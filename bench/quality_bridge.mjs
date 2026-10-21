import { readFile, mkdtemp, rm, access } from "node:fs/promises";
import { join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";

const MODEL = "gpt-6-astra";
const SDK_VERSION = "18.12.3";
const ENDPOINT = "https://chatgpt.com/backend-api/codex/responses";

export function validateRequest(request) {
    if (!request || request.schema_version !== 1 || !Number.isSafeInteger(request.request_id)) {
        throw new Error("Expected schema_version 1 and an integer request_id");
    }
    const prompt = request.prompt;
    if (!prompt || typeof prompt.version !== "string" || !prompt.version || !Array.isArray(prompt.messages) ||
        prompt.messages.length !== 2 || prompt.messages[0]?.role !== "system" || prompt.messages[1]?.role !== "user" ||
        prompt.messages.some(message => typeof message.content !== "string" || !message.content.trim())) {
        throw new Error("Expected one versioned system message and one independent user message");
    }
    return { systemPrompt: [prompt.messages[0].content],
             messages: [{ role: "user", content: prompt.messages[1].content, timestamp: Date.now() }], tools: [] };
}

export function validatePayload(payload, context) {
    if (!payload || payload.model !== MODEL || payload.previous_response_id ||
        (payload.tools && payload.tools.length) || payload.instructions !== context.systemPrompt[0] ||
        !Array.isArray(payload.input) || payload.input.length !== 1 || payload.input[0]?.role !== "user" ||
        payload.input[0].content?.length !== 1 || payload.input[0].content[0]?.type !== "input_text" ||
        payload.input[0].content[0].text !== context.messages[0].content || payload.store !== false ||
        (payload.service_tier && payload.service_tier !== "default")) {
        throw new Error("Inference payload violates independent no-tool judging isolation");
    }
}

function decodedEvents(raw) {
    return (raw.events ?? []).flatMap((event, index) => {
        try { return [{ value: JSON.parse(event.data), index }]; } catch { return []; }
    });
}

export function inferenceEnvelope(raw, outcome = {}) {
    const events = decodedEvents(raw);
    const terminal = events.findLast(({ value }) => ["response.completed", "response.done", "response.failed", "response.incomplete"].includes(value.type));
    const response = terminal?.value.response;
    const identity = typeof response?.model === "string" && response.model.trim() ? terminal : null;
    const actual = identity?.value.response.model ?? null;
    const evidence = identity ? { source: "raw inference response.model", event_index: identity.index,
        event_type: identity.value.type, response_id: identity.value.response.id ?? null,
        model: actual, requested_model: MODEL } : null;
    const created = response?.created_at;
    const date = typeof created === "number" && Number.isFinite(created) && created > 0 && created < 8640000000000
        ? new Date(created * 1000).toISOString() : typeof created === "string" ? created : raw.response_metadata?.date ?? null;
    const text = (response?.output ?? []).filter(item => item.type === "message" && item.role === "assistant")
        .flatMap(item => item.content ?? []).filter(item => item.type === "output_text" && typeof item.text === "string")
        .map(item => item.text).join("") || outcome.content || "";
    const errorText = JSON.stringify({ events: events.filter(({ value }) => value.type === "error" || value.type === "response.failed"),
        http_error: raw.http_error, status: raw.response_metadata?.status, error_status: outcome.error_status });
    const quota = raw.response_metadata?.status === 429 || outcome.error_status === 429 ||
        /usage_limit_reached|usage_limit_exceeded|insufficient_quota|rate_limit_exceeded|quota_exceeded/i.test(errorText);
    let status = "unresolved";
    let reason = "No confirmed terminal inference completion";
    if (quota) { status = "quota"; reason = "Subscription quota or rate limit reached; explicit resume required"; }
    else if (terminal?.value.type === "response.failed" || response?.status === "failed") {
        status = "failed"; reason = "Provider returned terminal inference failure";
    } else if (response?.status === "completed" && ["response.completed", "response.done"].includes(terminal?.value.type)) {
        if (!actual) reason = "Provider completed but did not expose response-level model identity";
        else if (!/^gpt-6-astra(?:-\d{4}-\d{2}-\d{2})?$/.test(actual)) reason = "Returned model is not the selected Astra judge; no fallback accepted";
        else if (!text.trim()) reason = "Provider completed without nonempty judgment content";
        else if (outcome.error || outcome.redispatch_blocked) reason = "Provider completion contradicted by transport failure";
        else { status = "completed"; reason = undefined; }
    }
    return { status, actual_model: actual, model_identity_evidence: evidence, content: text,
        response_date: date, raw, ...(reason ? { reason } : {}) };
}

function argumentsFor(argv) {
    const allowed = new Set(["--package-root", "--model", "--timeout-seconds", "--auth-db", "--credential-id"]);
    const args = {};
    for (let i = 0; i < argv.length; i += 2) {
        if (!allowed.has(argv[i]) || !argv[i + 1] || args[argv[i]]) throw new Error("Unsupported bridge arguments");
        args[argv[i]] = argv[i + 1];
    }
    if (args["--model"] !== MODEL || !args["--package-root"]) throw new Error("The selected Astra SDK package is required");
    const timeout = Number(args["--timeout-seconds"]);
    if (!Number.isFinite(timeout) || timeout <= 0) throw new Error("A positive finite timeout is required");
    return { ...args, timeout };
}

export async function runBridge(argv, request) {
    const context = validateRequest(request);
    const args = argumentsFor(argv);
    for (const name of Object.keys(process.env)) {
        if (/^(OPENAI_|CODEX_)/.test(name) || /^(PI_|OMP_).*(DEBUG|LOG)/.test(name)) delete process.env[name];
    }
    const raw = { events: [], response_metadata: null, observed_start_utc: new Date().toISOString(),
        bridge: { sdk: "@oh-my-pi/pi-ai", sdk_version: SDK_VERSION, runtime: `bun ${Bun.version}`,
            requested_model: MODEL, route: "Sign in with ChatGPT", inference_posts: 0,
            isolation: { agent_runtime: false, tools: 0, conversation_messages: 1, inherited_instructions: false,
                fresh_process: true, service_tier: "default", maximum_inference_posts: 1 } } };
    let auth;
    let ownedDirectory;
    let stage = "dependency preflight";
    const outcome = {};
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), args.timeout * 1000);
    try {
        const root = resolve(args["--package-root"]);
        const metadata = JSON.parse(await readFile(join(root, "package.json"), "utf8"));
        if (metadata.name !== "@oh-my-pi/pi-ai" || metadata.version !== SDK_VERSION) {
            throw new Error("Install the supported pinned @oh-my-pi/pi-ai package");
        }
        const logger = await import(pathToFileURL(Bun.resolveSync("@oh-my-pi/pi-utils/logger", root)).href);
        logger.setTransports({ file: false, console: false });
        const [{ AuthStorage }, { getBundledModel }, { discoverAuthStorage }, { streamOpenAICodexResponses }] = await Promise.all([
            import(pathToFileURL(join(root, "src/auth-storage.ts")).href),
            import(pathToFileURL(Bun.resolveSync("@oh-my-pi/pi-catalog/models", root)).href),
            import(pathToFileURL(join(root, "src/auth-broker/discover.ts")).href),
            import(pathToFileURL(join(root, "src/providers/openai-codex-responses.ts")).href),
        ]);
        const model = getBundledModel("openai-codex", MODEL);
        if (!model || model.provider !== "openai-codex" || model.api !== "openai-codex-responses" || model.requestModelId && model.requestModelId !== MODEL) {
            throw new Error("The installed SDK does not define the exact selected subscription model");
        }
        stage = "managed subscription authentication";
        if (args["--auth-db"]) {
            await access(args["--auth-db"]);
            auth = await AuthStorage.create(args["--auth-db"]);
            await auth.credentials.reload();
        } else auth = await discoverAuthStorage();
        const accounts = auth.oauth.accounts("openai-codex");
        const requestedId = args["--credential-id"] === undefined ? undefined : Number(args["--credential-id"]);
        if (requestedId !== undefined && (!Number.isSafeInteger(requestedId) || requestedId <= 0)) throw new Error("Invalid OAuth row selection");
        const selected = requestedId === undefined ? (accounts.length === 1 ? accounts[0] : undefined)
            : accounts.find(account => account.credentialId === requestedId);
        if (!selected) throw new Error("One existing OAuth account must be explicitly selected; no account rotation permitted");
        const credential = await auth.oauth.accessById("openai-codex", selected.credentialId, { modelId: MODEL, signal: controller.signal });
        if (!credential?.ok || !credential.accessToken) throw new Error("The selected managed OAuth account is unavailable");
        ownedDirectory = await mkdtemp(join(tmpdir(), "vrc-judge-"));
        process.chdir(ownedDirectory);
        stage = "subscription inference";
        const inferenceFetch = async (input, init) => {
            const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
            if (url !== ENDPOINT || (init?.method ?? "GET").toUpperCase() !== "POST") throw new Error("Only the selected subscription inference endpoint is allowed");
            if (raw.bridge.inference_posts !== 0) {
                outcome.redispatch_blocked = true;
                throw new Error("Automatic inference redispatch is disabled");
            }
            raw.bridge.inference_posts++;
            const response = await fetch(input, init);
            raw.response_metadata = { status: response.status, date: response.headers.get("date") };
            if (!response.ok) raw.http_error = await response.clone().text();
            return response;
        };
        const stream = streamOpenAICodexResponses({ ...model, baseUrl: "https://chatgpt.com/backend-api", headers: undefined }, context, {
            apiKey: credential.accessToken, signal: controller.signal, sessionId: crypto.randomUUID(),
            preferWebsockets: false, codexSseMaxAttempts: 1, acceptEmptyResponse: true, serviceTier: "default",
            reasoning: "medium", reasoningSummary: null, cwd: ownedDirectory, fetch: inferenceFetch,
            onPayload: payload => { validatePayload(payload, context); raw.bridge.payload_isolation_checked = true; },
            onSseEvent: event => {
                try {
                    raw.events.push(JSON.parse(JSON.stringify(event)));
                    if (event.data === "[DONE]") return;
                    const value = JSON.parse(event.data);
                    if (["error", "response.failed", "response.incomplete"].includes(value.type)) controller.abort();
                } catch { outcome.capture_error = true; controller.abort(); }
            },
            providerRetryWait: async () => { throw new Error("Automatic retry waits are disabled"); },
        });
        for await (const event of stream) {
            if (event.type === "done") outcome.content = event.message.content.filter(item => item.type === "text").map(item => item.text).join("");
            if (event.type === "error") { outcome.error = true; outcome.error_status = event.error.errorStatus ?? null; }
        }
        await stream.result();
        if (outcome.capture_error) outcome.error = true;
        return inferenceEnvelope(raw, outcome);
    } catch (error) {
        if (stage === "subscription inference") return inferenceEnvelope(raw, { ...outcome, error: true });
        return { status: "unavailable", actual_model: null, model_identity_evidence: null, content: "", response_date: null,
            reason: `Bridge prerequisite unavailable during ${stage}; no inference fallback attempted` +
                (stage === "dependency preflight" ? `: ${error.message}` : ""), raw };
    } finally {
        clearTimeout(timer);
        raw.observed_end_utc = new Date().toISOString();
        auth?.close();
        if (ownedDirectory) { process.chdir(tmpdir()); await rm(ownedDirectory, { recursive: true, force: true }); }
    }
}

if (import.meta.main) {
    console.log = console.warn = console.error = console.debug = () => {};
    let result;
    try { result = await runBridge(process.argv.slice(2), JSON.parse(await Bun.stdin.text())); }
    catch { result = { status: "failed", actual_model: null, model_identity_evidence: null, content: "", response_date: null,
        raw: null, reason: "Invalid bridge request or arguments; no inference attempted" }; }
    process.stdout.write(JSON.stringify(result));
}
