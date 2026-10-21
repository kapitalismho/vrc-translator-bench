"""Evidence-bound local cost reconciliation (stdlib only).

The specification is an operator's selected-evidence contract, not an account audit.
Provider export grammars are explicitly mapped; no live export is authenticated here.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from .cost_inputs import Inputs, TOKENS, identifier, number, timestamp
from .storage import atomic_json, utc_now

VERSION = "costs-v1"
SLACK_SECONDS = 30


def _json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items() if not key.startswith("_")}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def deduplicate(records):
    """Keep request alternatives; never turn uncertain copies into additive charges."""
    by_source_row, by_request, result = {}, {}, []
    fields = ("provider", "upstream_provider", "component", "granularity", "scope", "start", "end",
              "model", "key_alias", "currency", "cost", "audio_seconds", "submitted_audio_interval", *TOKENS)
    for row in records:
        source_key = (row["kind"], row["_source_hash"], row["_record_container"], row["source_rows"][0]["row"])
        request_key = (row["kind"], row["provider"], row["request_hash"]) if row["request_hash"] else None
        candidates = list(by_source_row.get(source_key, []))
        for other in by_request.get(request_key, []) if request_key else []:
            if all(other is not candidate for candidate in candidates):
                candidates.append(other)
        same = next((other for other in candidates if
                     all(other.get(field) == row.get(field) for field in fields)
                     and not (other["request_hash"] and row["request_hash"] and other["request_hash"] != row["request_hash"])), None)
        if same is not None:
            same["sources"] = sorted(set(same["sources"] + row["sources"]))
            same["source_rows"].extend(row["source_rows"])
            same["request_hash"] = same["request_hash"] or row["request_hash"]
            same["isolation_verified"] = same["isolation_verified"] and row["isolation_verified"]
            retained = same
        else:
            for other in candidates:
                other["exclusion"] = row["exclusion"] = "Conflicting duplicate request evidence"
                other.setdefault("conflicting_record_ids", []).append(row["id"])
                row.setdefault("conflicting_record_ids", []).append(other["id"])
            result.append(row)
            retained = row
        for index, key in ((by_source_row, source_key), (by_request, request_key)):
            if key is not None and all(retained is not other for other in index.get(key, [])):
                index.setdefault(key, []).append(retained)

    possible = {}
    for row in result:
        if row["granularity"] != "request":
            continue
        signature = (row["kind"], row["provider"], row["start"])
        group = possible.setdefault(signature, [])
        for other in group:
            if row["_source_hash"] == other["_source_hash"] or row["request_hash"] and other["request_hash"]:
                continue  # Separate same-source rows and distinct known IDs are legitimate calls.
            if any(row.get(field) is not None and other.get(field) is not None and row[field] != other[field]
                   for field in ("component", "model", "upstream_provider", "key_alias")):
                continue
            if any(row["scope"][key] is not None and other["scope"][key] is not None and row["scope"][key] != other["scope"][key]
                   for key in ("run", "wave")):
                continue
            if not row.get("exclusion"):
                row["exclusion"] = "Possible duplicate across sources without request identity; amount unknown"
            if not other.get("exclusion"):
                other["exclusion"] = "Possible duplicate across sources without request identity; amount unknown"
        group.append(row)
    return result


def _identity_matches(row, component, *, allow_unexpected=False):
    if row["component"] is not None and row["component"] != component["id"]:
        return False
    if row["provider"] != component["provider"]:
        return False
    constraints = (("key_alias", component.get("key_aliases", [])),)
    if not allow_unexpected:
        constraints += (("model", component.get("models", [])), ("upstream_provider", component.get("upstream_providers", [])))
    return not any(expected and row[field] is not None and row[field] not in expected for field, expected in constraints)


def attribute(row, windows, components):
    candidates, potential = [], []
    start = timestamp(row["start"]) if row["start"] is not None else None
    end = timestamp(row["end"]) if row["end"] else None
    for window in windows:
        if any(row["scope"].get(key) is not None and row["scope"][key] != window[key] for key in ("run", "wave")):
            continue
        begin, stop = timestamp(window["start"]), timestamp(window["end"]) + timedelta(seconds=SLACK_SECONDS)
        in_time = start is None or (begin <= start <= stop if row["granularity"] == "request" else start <= stop and end > begin)
        if not in_time:
            continue
        for component in components:
            if component["profile"] != window["profile"]:
                continue
            candidate = {"window_id": window["id"], "component_id": component["id"],
                         "run": window["run"], "wave": window["wave"]}
            if _identity_matches(row, component):
                candidates.append(candidate)
            elif _identity_matches(row, component, allow_unexpected=True):
                potential.append(candidate)
    potential = potential if not candidates else []
    row["attribution"] = {"status": "unresolved_identity" if potential else "unknown", "candidates": candidates,
                          "potential_candidates": potential, "window_id": None, "component_id": None,
                          "reason": "Request START time absent" if start is None else
                          "Unexpected actual model/upstream on a potentially matching key/window" if potential else "No matching observed window/identity"}
    if not candidates or start is None:
        return
    if row["granularity"] != "request":
        scopes = sorted({(item["run"], item["wave"]) for item in candidates})
        row["attribution"].update(status="coarse", scopes=[{"run": run, "wave": wave} for run, wave in scopes],
                                  reason="Bucket retained at export granularity; no chunk division")
        return
    if len(candidates) != 1:
        row["attribution"].update(status="ambiguous", reason="Multiple matching windows/components; no subtraction or allocation")
        return
    candidate = candidates[0]
    component = next(item for item in components if item["id"] == candidate["component_id"])
    missing = [field for field, required in (("model", True), ("key_alias", component.get("key_aliases")),
                                            ("upstream_provider", component.get("upstream_providers"))) if required and row[field] is None]
    isolated = row["kind"] != "provider_export" or row["isolation_verified"] and bool(row["isolation_evidence"])
    if missing or not isolated:
        row["attribution"].update(status="conditional", reason="Missing actual identity: " + ", ".join(missing) if missing else "Account isolation unverified; planned sole consumer is not proof")
        return
    row["attribution"].update(status="attributed", reason=None, window_id=candidate["window_id"], component_id=candidate["component_id"])


def exclude_overlaps(records):
    """Aggregate/detail overlap cannot produce an additive amount."""
    exports = [row for row in records if row["kind"] == "provider_export"]
    for left in exports:
        if left["granularity"] == "request":
            continue
        for right in exports:
            if right["granularity"] != "request" and left["id"] >= right["id"]:
                continue
            if left["provider"] != right["provider"]:
                continue
            if any(left[key] is not None and right[key] is not None and left[key] != right[key] for key in ("model", "key_alias")):
                continue
            if any(left["scope"].get(key) is not None and right["scope"].get(key) is not None and left["scope"][key] != right["scope"][key] for key in ("run", "wave")):
                continue
            if left["start"] is None or right["start"] is None:
                continue
            aggregate, detail = (right, left) if left["granularity"] == "request" else (left, right)
            a, b = timestamp(aggregate["start"]), timestamp(aggregate["end"])
            c = timestamp(detail["start"])
            d = timestamp(detail["end"]) if detail["granularity"] != "request" else c
            overlap = a <= c < b if detail["granularity"] == "request" else a < d and c < b
            if overlap:
                if detail["granularity"] == "request":
                    detail["exclusion"] = "Detail overlaps aggregate; aggregate retained without additive detail"
                    aggregate.setdefault("overlapping_detail_ids", []).append(detail["id"])
                else:
                    left["exclusion"] = right["exclusion"] = "Overlapping aggregate buckets; union amount unknown"


def validate_tables(tables):
    ids = set()
    for table in tables:
        identifier(table["id"])
        if table["id"] in ids:
            raise ValueError("Price table IDs must be unique")
        ids.add(table["id"])
        # Date is the inspected publication/snapshot date; validity timestamps determine applicability.
        from datetime import date
        date.fromisoformat(table["date"])
        if not table.get("evidence") or table.get("currency") != "USD":
            raise ValueError("Prices require dated evidence and explicit USD currency")
        if timestamp(table["valid_until"]) <= timestamp(table["valid_from"]):
            raise ValueError("Price validity interval must be positive")
        if table.get("basis") not in ("tokens", "audio_seconds"):
            raise ValueError("Prices require tokens or audio_seconds basis")
        if table["basis"] == "tokens":
            if type(table.get("input_includes_cached")) is not bool or type(table.get("output_includes_reasoning")) is not bool:
                raise ValueError("Token prices require explicit cache/reasoning containment")
            if set(table["rates"]) - {"input", "cached", "output", "reasoning"}:
                raise ValueError("Unknown token price rate")
            number(table["per_tokens"])
            if number(table["per_tokens"]) == 0:
                raise ValueError("Price token unit must be positive")
        else:
            number(table["per_second"])
        for rate in table.get("rates", {}).values():
            number(rate)


def calculate(row, tables, table_id=None):
    matches = [table for table in tables if table["provider"] == row["provider"] and table["model"] == row["model"]
               and (table_id is None or table["id"] == table_id) and row["start"] is not None
               and timestamp(table["valid_from"]) <= timestamp(row["start"]) < timestamp(table["valid_until"])]
    if len(matches) != 1:
        return {"value": None, "reason": "Exactly one applicable dated model price required", "price_table": None}
    table = matches[0]
    if table["basis"] == "audio_seconds":
        if row["audio_seconds"] is None:
            return {"value": None, "reason": "Actual audio sent/submitted duration absent; replay duration is not ASR usage", "price_table": table["id"]}
        amount = row["audio_seconds"] * number(table["per_second"])
        billed = {"audio_seconds": row["audio_seconds"]}
    else:
        if any(row[field] is None for field in TOKENS):
            return {"value": None, "reason": "Missing token categories; absence is not zero", "price_table": table["id"]}
        inp, cached, out, reasoning = (row[field] for field in TOKENS)
        if table["input_includes_cached"]:
            inp -= cached
        if table["output_includes_reasoning"]:
            out -= reasoning
        if inp < 0 or out < 0:
            return {"value": None, "reason": "Token containment inconsistent with observed categories", "price_table": table["id"]}
        billed = {"input": inp, "cached": cached, "output": out, "reasoning": reasoning}
        rates = table["rates"]
        # Contained tokens with no distinct price use the containing category's price, once.
        if "cached" not in rates:
            billed["input"] += billed.pop("cached")
        if "reasoning" not in rates:
            billed["output"] += billed.pop("reasoning")
        if any(key not in rates and quantity for key, quantity in billed.items()):
            return {"value": None, "reason": "Price missing for observed token category", "price_table": table["id"]}
        amount = sum((quantity * number(rates.get(key, 0)) for key, quantity in billed.items()), Decimal(0)) / number(table["per_tokens"])
    return {"value": amount, "reason": None, "price_table": table["id"], "billed_units": billed,
            "method": "usage_based_calculation; billing rounding/minimums not established"}


def usage_summary(rows):
    logical = [row for row in rows if row.get("event") == "request_end"]
    attempts = [row for row in rows if row.get("event") != "request_end"]
    observed = {key: sum(row[key] is not None for row in attempts) for key in (*TOKENS, "audio_seconds")}
    return {"calls": len(attempts), "logical_requests": len(logical),
            "models": sorted({row["model"] for row in attempts if row["model"] is not None}),
            "request_starts": [row["start"] for row in attempts],
            "statuses": {status: sum(row.get("status") == status for row in attempts) for status in ("success", "error", "cancelled")},
            **{key: {"known": sum((row[key] for row in attempts if row[key] is not None), Decimal(0)) if observed[key] else None,
                     "observed_calls": observed[key], "total_calls": len(attempts)} for key in (*TOKENS, "audio_seconds")}}


def _coverage(component, windows):
    claim = component.get("coverage", {})
    selected = claim.get("window_ids", [])
    known = {row["id"] for row in windows if row["profile"] == component["profile"]}
    if len(selected) != len(set(selected)) or not set(selected).issubset(known):
        raise ValueError("Component coverage must select unique observed windows of its profile")
    return {"window_ids": selected, "complete_claim": claim.get("complete") is True, "evidence": claim.get("evidence"),
            "claim_type": "operator_supplied_not_independent_export_completeness_proof"}


def component_report(component, records, windows, tables):
    cid = component["id"]
    coverage = _coverage(component, windows)
    selected = set(coverage["window_ids"])
    matching = [row for row in records if row["attribution"]["component_id"] == cid and row["attribution"]["window_id"] in selected]
    usable = [row for row in matching if not row.get("exclusion")]
    provider = [row for row in usable if row["kind"] == "provider_export"]
    internal = [row for row in usable if row["kind"] in ("pp_log", "submitted_audio") and row.get("event") != "request_end"]
    uncertain = [row for row in records if
                 (any(candidate["component_id"] == cid and candidate["window_id"] in selected
                      for candidate in row["attribution"]["candidates"] + row["attribution"]["potential_candidates"])
                  or row["component"] == cid and not row["attribution"]["candidates"])
                 and (row["attribution"]["status"] != "attributed" or row.get("exclusion"))]
    treatment = component["treatment"]
    result = {"id": cid, "profile": component["profile"], "provider": component["provider"], "treatment": treatment,
              "services": component.get("services", []), "services_evidence": component.get("services_evidence"),
              "coverage": coverage, "access": access_report(component.get("access", {})),
              "internal_usage": usage_summary(internal), "provider_records": len(provider),
              "approximate_start_records": sum(bool(row.get("start_basis")) for row in usable),
              "all_bound_internal_usage": usage_summary([row for row in records if row["component"] == cid and row["kind"] != "provider_export"]),
              "unresolved_record_ids": [row["id"] for row in uncertain], "known_subtotal": None, "cost": None,
              "currency": "USD", "status": "unknown", "reason": None}
    calculations = [{"record_id": row["id"], **calculate(row, tables, component.get("price_table"))} for row in internal]
    result["internal_calculation"] = {"known_subtotal": sum((row["value"] for row in calculations if row["value"] is not None), Decimal(0)) if calculations else None,
                                      "priced_calls": sum(row["value"] is not None for row in calculations), "calls": len(internal), "records": calculations}
    cost_uncertain = [row for row in uncertain if row["kind"] == "provider_export"] if treatment == "provider" else [row for row in uncertain if row.get("event") != "request_end"]
    complete = bool(selected and coverage["complete_claim"] and coverage["evidence"] and not cost_uncertain)
    if treatment == "subscription":
        result.update(status="subscription", reason="Subscription access marker; actual subscription price not assigned per token")
        result["supplementary_api_equivalent"] = result.pop("internal_calculation")
        return result
    if treatment == "free":
        access = component.get("access", {})
        charged = [row for row in matching if row["kind"] == "provider_export" and row["cost"] is not None and row["cost"] > 0]
        if charged:
            result.update(reason="Observed positive provider charge contradicts asserted free access",
                          access_conflict_record_ids=[row["id"] for row in charged])
            return result
        eligible = access.get("observed_eligible") is True and bool(access.get("evidence")) and selected.issubset(set(access.get("window_ids", [])))
        if complete and eligible:
            result.update(cost=Decimal(0), known_subtotal=Decimal(0), status="complete", reason="Zero only for evidenced observed eligible windows")
        else:
            result["reason"] = "Observed free eligibility and complete evidence covering selected windows required"
        return result
    if treatment == "provider":
        amounts = [row["cost"] for row in provider if row["currency"] == "USD" and row["cost"] is not None]
        result["known_subtotal"] = sum(amounts, Decimal(0)) if amounts else None
        complete = complete and bool(provider) and len(amounts) == len(provider)
        result["reason"] = "Attributable complete provider records required" if not complete else None
        if component["profile"] == "PP1":
            internal_value = result["internal_calculation"]["known_subtotal"]
            priced = result["internal_calculation"]["priced_calls"]
            comparable = bool(provider and internal and priced == len(internal))
            result["reconciliation"] = {"provider_governs": True, "provider_amount": result["known_subtotal"],
                                        "internal_usage_calculation": internal_value,
                                        "difference_provider_minus_internal": result["known_subtotal"] - internal_value if comparable and result["known_subtotal"] is not None else None,
                                        "provider_calls": len(provider), "internal_calls": len(internal), "priced_internal_calls": priced,
                                        "coverage_equal_claim": component.get("reconciliation_coverage_equal") is True,
                                        "interpretation": "Difference compares selected observed records, not a billing audit or resolution of shared-account remainder"}
    elif treatment == "usage":
        amounts = [row["value"] for row in calculations if row["value"] is not None]
        result["known_subtotal"] = sum(amounts, Decimal(0)) if amounts else None
        complete = complete and bool(internal) and len(amounts) == len(internal)
        result["reason"] = "Complete actual usage and dated prices required" if not complete else None
    elif treatment == "unknown":
        complete = False
        result["reason"] = component.get("missing_reason", "Usage/access evidence absent")
    else:
        raise ValueError("Unknown cost component treatment")
    if complete:
        result.update(cost=result["known_subtotal"], status="complete")
    elif result["known_subtotal"] is not None:
        result["status"] = "partial"
    return result


def access_report(access):
    result = {key: access.get(key) for key in ("condition", "observed_eligible", "evidence", "window_ids", "quota", "limit_status", "scope_start", "reached_at")}
    if isinstance(access.get("quota"), dict):
        result["quota"] = {key: access["quota"][key] for key in ("unit", "observed_limit", "remaining", "period", "reset_at") if key in access["quota"]}
    state = access.get("limit_status", "unknown")
    if state not in ("reached", "not_observed", "unknown"):
        raise ValueError("Quota limit_status requires reached, not_observed or unknown")
    result["limit_status"] = state
    result["minutes_to_limit"] = None
    if state == "reached" and access.get("scope_start") and access.get("reached_at"):
        elapsed = (timestamp(access["reached_at"]) - timestamp(access["scope_start"])).total_seconds() / 60
        if elapsed < 0:
            raise ValueError("Quota reached timestamp precedes scope start")
        result["minutes_to_limit"] = elapsed
    return result


def validate_components(components):
    for component in components:
        profile, provider, treatment = (component[key] for key in ("profile", "provider", "treatment"))
        if provider == "openrouter" and profile in ("PP1", "VRCT3", "VRCS1", "VRCS2") and treatment != "provider":
            raise ValueError("This profile's OpenRouter component must use governing provider records")
        if profile == "VRCLT2" and provider == "qwen" and treatment != "provider":
            raise ValueError("VRCLT2 Qwen cost requires provider records")
        if profile == "PP2" and provider != "gemini" and treatment != "subscription":
            raise ValueError("PP2 translation must remain a subscription marker")
        if "services" not in component:
            continue  # Components remain usable, but missing inventory never completes a profile.
        services = component["services"]
        if not isinstance(services, list) or not services or any(service not in ("translation", "asr") for service in services) or len(services) != len(set(services)):
            raise ValueError("Component services must be a unique nonempty list of translation/asr")
        if "services_evidence" in component and (not isinstance(component["services_evidence"], str) or not component["services_evidence"].strip()):
            raise ValueError("Service evidence must be a nonempty publication-safe explanation")
        if profile in ("PP1", "PP2"):
            if len(services) != 1:
                raise ValueError("PP1/PP2 require separate translation and Gemini ASR components")
            if services == ["asr"] and (provider != "gemini" or treatment not in ("usage", "free", "unknown")):
                raise ValueError("PP1/PP2 ASR must be a separately evidenced Gemini component")
            if services == ["translation"] and (provider == "gemini" or profile == "PP1" and provider != "openrouter"):
                raise ValueError("Known PP translation provider obligations cannot be relabelled")


def profile_report(profile, components):
    selected = [row for row in components if row["profile"] == profile]
    required, covered, issues = {"translation", "asr"}, set(), []
    for component in selected:
        services = component["services"]
        if not services:
            issues.append(component["id"] + ": service inventory missing")
        elif len(services) == 2 and not component["services_evidence"]:
            issues.append(component["id"] + ": combined service evidence missing")
        else:
            covered.update(services)
    missing = sorted(required - covered)
    same_coverage = len({tuple(sorted(row["coverage"]["window_ids"])) for row in selected}) == 1
    complete = not missing and not issues and same_coverage and all(row["cost"] is not None for row in selected)
    return {"profile": profile, "component_ids": [row["id"] for row in selected],
            "required_services": sorted(required), "covered_services": sorted(covered),
            "missing_services": missing, "inventory_issues": issues,
            "window_ids": selected[0]["coverage"]["window_ids"] if same_coverage else None,
            "cost": sum((row["cost"] for row in selected), Decimal(0)) if complete else None,
            "known_numeric_subtotal": sum((row["known_subtotal"] for row in selected if row["known_subtotal"] is not None), Decimal(0)) if any(row["known_subtotal"] is not None for row in selected) else None,
            "reason": "Missing required services: " + ", ".join(missing) if missing else
                      "; ".join(issues) if issues else None if complete else "Missing, partial, subscription or unequal-coverage component prevents complete numeric total"}


def denominator_report(definition, components, profiles, windows):
    identifier(definition["id"])
    selected = definition["window_ids"]
    known = {row["id"]: row for row in windows}
    if not selected or len(selected) != len(set(selected)) or not set(selected).issubset(known):
        raise ValueError("Denominators require unique observed windows")
    component_ids = definition["component_ids"]
    chosen = [row for row in components if row["id"] in component_ids]
    if len(chosen) != len(component_ids) or not chosen:
        raise ValueError("Denominators require unique known component IDs")
    scope = definition.get("scope", "profile")
    if scope not in ("profile", "component"):
        raise ValueError("Denominator scope must be profile or component")
    profile_ids = {row["profile"] for row in chosen}
    if len(profile_ids) != 1:
        raise ValueError("A denominator must identify one profile's component inventory")
    profile = next(row for row in profiles if row["profile"] in profile_ids)
    supported = all(row["cost"] is not None and set(row["coverage"]["window_ids"]) == set(selected) for row in chosen)
    reason = None if supported else "Complete component costs on exactly the covered subset required"
    if scope == "profile" and (profile["cost"] is None or set(component_ids) != set(profile["component_ids"])):
        supported = False
        reason = "Complete profile service/component inventory required; " + (profile["reason"] or "declared components omitted")
    if not definition.get("evidence"):
        supported, reason = False, "Explicit real denominator evidence required"
    seconds = number(definition["replay_seconds"]) if definition.get("replay_seconds") is not None else None
    sentences = number(definition["reference_sentences"]) if definition.get("reference_sentences") is not None else None
    observed = sum((number(known[key]["replayed_seconds"]) if known[key].get("replayed_seconds") is not None else
                    number((timestamp(known[key]["end"]) - timestamp(known[key]["start"])).total_seconds()) for key in selected), Decimal(0))
    consistent = seconds == observed if seconds else None
    if consistent is False:
        supported, reason = False, "Supplied replay_seconds contradict selected observed replay duration"
    total = sum((row["cost"] for row in chosen), Decimal(0)) if supported else None
    populations = sorted({known[key].get("population") or "unspecified" for key in selected})
    return {"id": definition["id"], "scope": scope, "cost_kind": "profile_total" if scope == "profile" else "component_subtotal",
            "profile": profile["profile"], "window_ids": selected, "component_ids": component_ids,
            "population": definition["population"], "window_populations": populations, "mixed_populations": len(populations) > 1,
            "evidence": definition.get("evidence"), "replay_seconds": seconds, "observed_replay_seconds": observed,
            "replay_seconds_consistent": consistent, "reference_sentences": sentences, "cost": total,
            "per_replayed_conversation_hour": total * 3600 / seconds if total is not None and seconds else None,
            "per_1000_reference_sentences": total * 1000 / sentences if total is not None and sentences else None,
            "reason": reason if reason else None if seconds and sentences else "Explicit real positive denominators required"}


def derive(spec_path, output_path):
    inputs = Inputs(spec_path)
    spec = inputs.spec
    components = spec.get("components", [])
    ids = [identifier(row["id"]) for row in components]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Cost components require unique IDs")
    tables = spec.get("price_tables", [])
    validate_tables(tables)
    validate_components(components)
    windows, attempts = inputs.windows()
    records = deduplicate(inputs.records())
    for row in records:
        attribute(row, windows, components)
    exclude_overlaps(records)
    reports = [component_report(component, records, windows, tables) for component in components]
    coarse = []
    for row in records:
        if row["attribution"]["status"] == "coarse":
            attributable = row["isolation_verified"] and bool(row["isolation_evidence"]) and bool(row["scope_evidence"]) and all(row["scope"].get(key) for key in ("run", "wave")) and not row.get("exclusion")
            coarse.append({"record_id": row["id"], "scope": row["scope"], "candidate_scopes": row["attribution"]["scopes"],
                           "granularity": row["granularity"], "cost": row["cost"] if attributable and row["currency"] == "USD" else None,
                           "known_export_amount": row["cost"], "currency": row["currency"], "mixed_workload_possible": not row["isolation_verified"],
                           "reason": "Known export bucket/wave only; not a chunk amount" if attributable else "Coarse scope/isolation/overlap unresolved"})
    profile_reports = [profile_report(profile, reports) for profile in sorted({row["profile"] for row in reports})]
    unmatched = sum(not row["attribution"]["candidates"] for row in records)
    synthetic = spec.get("synthetic", False) or any(item.get("synthetic", False) for item in inputs.provenance) or any(row.get("actual_dac_observed") is False for row in windows)
    result = {"version": VERSION, "generated_at": utc_now(), "currency": "USD", "synthetic": synthetic,
              "privacy": "Selected normalized benchmark-candidate evidence only; no raw rows, request IDs, credentials or input paths. Operator must map only nonsecret model/aliases and supply publication-safe labels/evidence. Source hashes can identify complete private files; no account-audit or automatic redaction claim.",
              "rules": {"request_time": "START only; timezone-aware; inclusive window start through end+30s", "slack_seconds": SLACK_SECONDS,
                        "ambiguity": "Retain candidates once; never subtract uncertain PP estimates to derive VRCS2", "coarse": "Retain bucket/wave; never split into chunks",
                        "denominators": "Explicit actual selected subset only; plans/attempt wall duration never substitute",
                        "excluded_costs": ["power", "setup", "hardware", "TTS"]},
              "provenance": inputs.provenance,
              "price_tables": [{key: table[key] for key in ("id", "provider", "model", "date", "valid_from", "valid_until", "currency", "basis", "per_tokens", "rates", "per_second", "input_includes_cached", "output_includes_reasoning", "evidence") if key in table} for table in tables],
              "windows": windows, "attempts": attempts,
              "records": records, "unmatched_record_count": unmatched,
              "components": reports, "profiles": profile_reports, "coarse_costs": coarse,
              "denominators": [denominator_report(row, reports, profile_reports, windows) for row in spec.get("denominators", [])]}
    output_path = Path(output_path).resolve()
    if output_path in inputs.paths or output_path.with_name(output_path.name + ".tmp") in inputs.paths:
        raise ValueError("Cost output must not overwrite a raw input")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = _json(result)
    atomic_json(output_path, result)
    return result
