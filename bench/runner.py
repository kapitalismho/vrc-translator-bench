from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from .activity import exclusive_activity
from .adapter import Adapter, OperationalError, ProductError, redact
from .audio import ClockPlayback, Playback
from .native import NativeSink
from .plan import implementation_provenance, verify_audio
from .storage import Journal, Ledger, RunLock, utc_now


TERMINAL = {"done", "product_failure"}


def _continuity(value):
    # A live controller, open socket or surviving process is not opportunity proof.
    if not isinstance(value, dict):
        return {"continuous": None, "evidence": [], "gaps": []}
    return {"continuous": value.get("continuous") if type(value.get("continuous")) is bool else None,
            "evidence": value.get("evidence", []), "gaps": value.get("gaps", [])}


def _established(observations):
    return bool(observations) and all(item["continuous"] is True and item["evidence"] and not item["gaps"] for item in observations)


class _AttemptJournal(Journal):
    def __init__(self, path):
        super().__init__(path)
        self.output_receipts = []
        self.evidence_lock = threading.Lock()

    def append(self, record):
        with self.evidence_lock:
            text = any(isinstance(record.get(field), str) and record[field].strip()
                       for field in ("translated_text", "display_text"))
            texts = record.get("translated_texts")
            text = text or (isinstance(texts, list) and any(isinstance(value, str) and value.strip() for value in texts))
            if record.get("record") == "native_output_event" and record.get("capture_phase") == "input" and text:
                self.output_receipts.append((record.get("input_channel"), record.get("collector_received_monotonic")))
            super().append(record)

    def outputs_between(self, windows):
        with self.evidence_lock:
            channels, ambiguous = set(), False
            for channel, received in self.output_receipts:
                if channel not in windows or type(received) is not int:
                    ambiguous = True
                elif windows[channel][0] <= received <= windows[channel][1]:
                    channels.add(channel)
            return channels, ambiguous


class Runner:
    def __init__(self, root, plan, synthetic=False, resume=False):
        if plan.get("schema_version") != 2:
            raise OperationalError("Only episode schema_version 2 can run or resume")
        if synthetic != bool(plan.get("synthetic", False)):
            raise OperationalError("Synthetic plans require --audio-backend clock; real plans require wasapi")
        self.root, self.plan = Path(root), plan
        self.synthetic, self.resume = synthetic, resume
        self.session = uuid.uuid4().hex
        self.ledger = Ledger(root)
        self.profiles = {profile["id"]: profile for profile in plan["profiles"]}
        self.episodes = {episode["episode_id"]: episode for episode in plan["episodes"]}
        self.adapters, self.open_attempts = {}, {}
        self.running_profiles = set()
        self.sink = None
        self.wave = None
        self.blocked_scopes = set()

    def _adapter(self, profile):
        if profile not in self.adapters:
            self.adapters[profile] = Adapter(self.profiles[profile], self.root, self.session)
        return self.adapters[profile]

    def _context(self, item, attempt):
        return {"episode_id": item["episode_id"], "pass_id": item["pass_id"], "wave": item["wave"],
                "roles": item["roles"], "attempt": attempt["id"], "capture_phase": "preparation"}

    def _begin(self, work, item):
        attempt = self.ledger.begin(work, self.resume)
        journal = _AttemptJournal(self.root / attempt["trace"])
        self.open_attempts[work["profile"]] = attempt, journal
        journal.append({"record": "attempt_start", "t_ns": time.perf_counter_ns(), "wall": utc_now(),
                        "run": self.plan["run_id"], "profile": work["profile"], "pass_index": work["pass_index"],
                        "kind": item["kind"], "resumed": self.resume, "clock_session": self.session,
                        **self._context(item, attempt)})
        self.sink.attach(work["profile"], self._context(item, attempt), journal)

    def _record(self, profile, record):
        self.open_attempts[profile][1].append(redact(record))

    def _finish(self, profile, state, reason=None, detail=None, outcome=None):
        attempt, journal = self.open_attempts.pop(profile)
        self.sink.detach(profile)
        journal.append({"record": "attempt_end", "t_ns": time.perf_counter_ns(), "wall": utc_now(),
                        "state": state, "reason": reason, "detail": redact(detail or {})})
        trace, checksum = journal.finalize(".invalid.jsonl" if state == "invalid" else ".jsonl")
        self.ledger.finish(attempt, state, reason, trace, checksum, redact(detail or {}), outcome)
        self.ledger.manifest(self.plan)

    def _claim_capture(self, profile, reason):
        if profile not in self.running_profiles:
            self.running_profiles.add(profile)
            self.ledger.record("capture_ownership", {"profile": profile, "owned": True, "reason": reason,
                                                       "session": self.session, "wave": self.wave})

    def _state(self, profile, expected=None):
        state = self._adapter(profile).call("read_state")
        if state.get("running") is True:
            self._claim_capture(profile, "observed_running")
        self.ledger.record("application_state", {"profile": profile, "state": redact(state), "requested": expected})
        if expected and any(state.get(key) != value for key, value in expected.items()):
            raise OperationalError(f"{profile} effective settings mismatch")
        return state

    def _stop(self, profile):
        adapter = self._adapter(profile)
        if adapter.call("stop").get("running") is not False or self._state(profile).get("running") is not False:
            raise OperationalError(f"{profile} did not confirm stopped capture")
        self.running_profiles.discard(profile)
        self.ledger.record("capture_ownership", {"profile": profile, "owned": False,
                                                   "reason": "confirmed_stop", "session": self.session})

    def _reconcile_capture(self):
        owned = sorted(self.ledger.owned_profiles())
        # Claim every prior owner before asking any controller: cleanup must survive
        # failure to query the first one, including terminal work that is not replayed.
        for profile in owned:
            if profile not in self.profiles:
                raise OperationalError(f"Previously owned profile absent from frozen plan: {profile}")
            self._claim_capture(profile, "resume_reconciliation")
        for profile in owned:
            state = self._state(profile)
            self.ledger.record("capture_reconciliation", {"profile": profile, "state": redact(state), "session": self.session})
            if state.get("running") is False:
                self.running_profiles.discard(profile)
                self.ledger.record("capture_ownership", {"profile": profile, "owned": False, "reason": "observed_stopped"})
            elif state.get("running") is not True:
                raise OperationalError(f"{profile} reconciliation did not establish capture state")
            else:
                self._stop(profile)

    def _prepare(self, profile, item):
        adapter = self._adapter(profile)
        spec = self.profiles[profile]
        episode = self.episodes[item["episode_id"]]
        preflight = adapter.call("preflight", profile=spec, episode=episode, pass_spec=item)
        self.ledger.record("profile_metadata", {"profile": profile, "episode_id": item["episode_id"],
                                                "pass_id": item["pass_id"], "metadata": redact(preflight.get("metadata", {}))})
        if preflight.get("supported") is False:
            self._finish(profile, "done", preflight.get("reason", "unsupported"), {"opportunity": "not_played"}, "N/A")
            return False
        if preflight.get("ready") is not True:
            raise OperationalError(f"{profile} preflight is not ready")
        state = self._state(profile)
        if state.get("running") is True:
            self._stop(profile)
        elif state.get("running") is not False:
            raise OperationalError("Capture state unknown before session reset")
        self.sink.stop(profile)
        reset = adapter.call("reset_session", episode_id=item["episode_id"], pass_id=item["pass_id"])
        self._record(profile, {"record": "session_reset", "t_ns": time.perf_counter_ns(), **reset})
        if reset.get("reset") is not True or not reset.get("basis") or not reset.get("evidence"):
            raise OperationalError("Independent episode/pass requires evidenced conversation reset, not screen clear")
        channels = {channel: {**binding, "input_device": spec["routes"][channel]["input_device"],
                              "output_device": spec["routes"][channel]["output_device"]}
                    for channel, binding in item["roles"].items()}
        expected = {**spec["expected_state"], "channels": channels}
        adapter.call("configure", requested_state=expected)
        self._state(profile, expected)
        identity = adapter.call("identity")
        self.sink.identity(profile, identity)
        self.sink.start(profile)
        self._claim_capture(profile, "start_requested")
        if adapter.call("start").get("running") is not True:
            raise OperationalError(f"{profile} did not confirm capture running")
        if self._state(profile, expected).get("running") is not True:
            raise OperationalError("Effective capture is not running")
        adapter.call("begin_pass", pass_spec=item, attempt=self.open_attempts[profile][0]["id"])
        return True

    def _block_limit(self, profile, error):
        scope = error.scope or self.profiles[profile].get("quota_scope", profile)
        self.blocked_scopes.add(scope)
        self.blocked_scopes.add(profile)
        self.ledger.record("quota_limit", {"profile": profile, "scope": scope,
                                           "future_work": "pending_not_played", "reached_ns": error.reached_ns})

    def _health(self, profiles, observations, errors):
        for profile in profiles:
            try:
                adapter = self._adapter(profile)
                adapter.observe()
                health = adapter.call("liveness")
                if health.get("alive") is False:
                    raise ProductError("crash", "Application process exited")
                if health.get("failure"):
                    failure = health["failure"]
                    raise ProductError(failure["reason"], failure.get("message", ""), failure.get("scope"))
            except ProductError as error:
                health = {"alive": False if error.reason == "crash" else None}
                errors[profile].append({"reason": error.reason, "message": str(error),
                                        "reached_ns": error.reached_ns, "reached_wall": error.reached_wall})
                if error.reason == "limit":
                    self._block_limit(profile, error)
            collector = _continuity(self.sink.continuity(profile))
            entry = {"record": "continuity", "t_ns": time.perf_counter_ns(), "alive": health.get("alive"),
                     "app": _continuity(health.get("app_continuity")),
                     "input": _continuity(health.get("input_continuity")), "collector": collector}
            observations[profile].append(entry)
            self._record(profile, entry)

    def _quiet(self, item, profiles, observations, errors):
        started = time.perf_counter_ns()
        deadline = started + round(item["quiet_max_wait_seconds"] * 1e9)
        self.sink.phase(profiles, "quiet_precondition")
        next_health = 0
        while True:
            self.sink.check()
            if time.perf_counter_ns() >= next_health:
                self._health(profiles, observations, errors)
                next_health = time.perf_counter_ns() + 1_000_000_000
            with self.sink.lock:
                now = time.perf_counter_ns()
                quiet = {profile: now - max(started, self.sink.last_output.get(profile) or started)
                         >= round(item["quiet_seconds"] * 1e9) for profile in profiles}
                met = all(quiet.values())
                if met or now >= deadline:
                    result = {"record": "nonspeech_quiet_wait", "start_ns": started, "end_ns": now,
                              "status": "achieved" if met else "timeout", "quiet_precondition_met": met,
                              "unresolved_carryover": not met, "profiles": quiet}
                    self.sink.record(result)
                    for profile in profiles:
                        self._record(profile, result)
                    return result
            time.sleep(0.01)

    def _players(self, items, profiles):
        players, bindings = {}, {}
        occupied = {}
        try:
            for profile in profiles:
                item = items[profile]
                bindings[profile] = {}
                for channel, binding in item["roles"].items():
                    route = self.profiles[profile]["routes"][channel]
                    source = self.episodes[item["episode_id"]]["roles"][binding["role"]]
                    key = (str(route["output_device"]), source["audio_sha256"])
                    if key not in players:
                        player = (ClockPlayback if self.synthetic else Playback)(source["audio"], route["output_device"])
                        players[key] = player
                        if not self.synthetic:
                            device = player.devices["output"]
                            calibration = route["calibration"]["devices"]["output"]
                            if device[0] != calibration[0] or device[1]["name"] != calibration[1]["name"]:
                                raise OperationalError("Playback device does not match measured route calibration")
                        physical = key[0] if self.synthetic else str(player.devices["output"][0])
                        if physical in occupied and occupied[physical] != key:
                            raise OperationalError("Different role buffers cannot share one physical output device")
                        occupied[physical] = key
                    bindings[profile][channel] = (key, route, source)
            return players, bindings
        except BaseException:
            for player in players.values():
                player.close()
            raise

    def _capture(self, execution_round):
        work = [work for index in execution_round["pass_indices"] for work in self.ledger.work(index)
                if work["state"] not in TERMINAL
                and work["profile"] not in self.blocked_scopes
                and self.profiles[work["profile"]].get("quota_scope", work["profile"]) not in self.blocked_scopes]
        if not work:
            return
        items = {task["profile"]: self.plan["passes"][task["pass_index"]] for task in work}
        common = next(iter(items.values()))
        verify_audio(self.episodes[common["episode_id"]])
        active, players = [], {}
        observations, errors = {}, {}
        try:
            for task in work:
                profile = task["profile"]
                if profile in self.blocked_scopes or self.profiles[profile].get("quota_scope", profile) in self.blocked_scopes:
                    continue
                item = items[profile]
                self._begin(task, item)
                observations[profile], errors[profile] = [], []
                try:
                    if self._prepare(profile, item):
                        active.append(profile)
                except ProductError as error:
                    if error.reason == "limit":
                        self._block_limit(profile, error)
                    self._finish(profile, "product_failure", error.reason,
                                 {"opportunity": "not_played", "message": str(error)}, "unknown")
            if not active:
                return
            players, bindings = self._players(items, active)
            quiet = self._quiet(common, active, observations, errors) if "quiet_seconds" in common else None
            self.sink.phase(active, "input", **({} if quiet is None else {key: quiet[key] for key in ("quiet_precondition_met", "unresolved_carryover")}))
            # Schedule all streams against the same host monotonic clock. WASAPI
            # callbacks prepend silence up to this epoch. Each device's actual DAC
            # origin is recorded; unrelated hardware clocks are not sample locked.
            scheduled = time.perf_counter_ns() + 200_000_000
            for player in players.values():
                player.start(scheduled)
            positions = {key: 0 for key in players}
            sources_sent, horizons, profile_deadlines = set(), {}, {}
            next_health, deadline = 0, None
            while True:
                now = time.perf_counter_ns()
                self.sink.check()
                for key, player in players.items():
                    player.check()
                    if player.first_dac_ns is None and now > scheduled + 10_000_000_000:
                        raise OperationalError("Playback produced no actual source callback within ten seconds")
                    for callback in player.records[positions[key]:]:
                        for profile in active:
                            for channel, (stream_key, _, _) in bindings[profile].items():
                                if stream_key == key:
                                    self._record(profile, {"record": "audio_callback", "input_channel": channel, **callback})
                    positions[key] = len(player.records)
                for profile in active:
                    item = items[profile]
                    for channel, (key, route, source) in bindings[profile].items():
                        player = players[key]
                        offset = 0 if self.synthetic else route["calibration"]["offset_ns"]
                        if player.first_dac_ns is not None and (profile, channel) not in sources_sent:
                            record = {"record": "source_playback", "profile": profile, **self._context(item, self.open_attempts[profile][0]),
                                      "input_channel": channel, **item["roles"][channel], "clock_session": self.session, "capture_phase": "input",
                                      "playback_dac_start_ns": player.first_dac_ns, "scheduled_start_ns": scheduled,
                                      "actual_dac_observed": not self.synthetic, "audio_sha256": source["audio_sha256"],
                                      "calibration": route["calibration"], "input_origin_ns": None if self.synthetic else player.first_dac_ns + offset,
                                      "synchronization": "host-monotonic scheduled start; independent device clocks, not sample-accurate"}
                            self.sink.source(profile, record)
                            self._record(profile, record)
                            sources_sent.add((profile, channel))
                        speech_end = player.source_time_ns(item["common_last_speech_seconds"])
                        if speech_end is not None and (profile, channel) not in horizons:
                            horizons[(profile, channel)] = speech_end + offset + 15_000_000_000
                            self._record(profile, {"record": "role_horizon", "input_channel": channel,
                                                   "common_last_speech_seconds": item["common_last_speech_seconds"],
                                                   "common_speech_end_dac_ns": speech_end,
                                                   "calibration_offset_ns": None if self.synthetic else offset,
                                                   "role_horizon_ns": horizons[(profile, channel)],
                                                   "synthetic": self.synthetic})
                if deadline is None and len(horizons) == sum(len(value) for value in bindings.values()):
                    deadline = max(horizons.values())
                    for profile in active:
                        profile_deadlines[profile] = max(horizons[(profile, channel)] for channel in bindings[profile])
                        self._record(profile, {"record": "observation_window", "observation_end_ns": profile_deadlines[profile],
                                               "round_collection_deadline_ns": deadline,
                                               "role_horizons_ns": {channel: horizons[(profile, channel)] for channel in bindings[profile]},
                                               "synthetic": self.synthetic})
                if now >= next_health:
                    self._health(active, observations, errors)
                    next_health = time.perf_counter_ns() + 1_000_000_000
                if deadline is not None and now >= deadline and all(player.done.is_set() for player in players.values()):
                    break
                time.sleep(0.01)
            self.sink.phase(active, "observation_end")
            self._health(active, observations, errors)
            self.sink.check()
            ended = time.perf_counter_ns()
            for profile in active:
                item = items[profile]
                continuity = {kind: _established([entry[kind] for entry in observations[profile]])
                              for kind in ("app", "input", "collector")}
                windows = {channel: (players[key].first_dac_ns + (0 if self.synthetic else route["calibration"]["offset_ns"]),
                                     profile_deadlines[profile]) for channel, (key, route, _) in bindings[profile].items()}
                channels_with_output, attribution_unknown = self.open_attempts[profile][1].outputs_between(windows)
                opportunity = (all(continuity.values()) and not self.synthetic and not attribution_unknown
                               and not (quiet and not quiet["quiet_precondition_met"]))
                role_outcomes = {binding["role"]: {
                    "input_channel": channel,
                    "status": ("control" if item["kind"] == "C1" else "output_observed" if channel in channels_with_output
                               else "product_no_output" if opportunity else "unknown_no_output")}
                    for channel, binding in item["roles"].items()}
                statuses = {value["status"] for value in role_outcomes.values()}
                outcome = next(iter(statuses)) if len(statuses) == 1 else "mixed_role_outcomes"
                detail = {"continuity_established": continuity, "opportunity_established": opportunity,
                          "output_attribution_unknown": attribution_unknown,
                          "synthetic": self.synthetic, "observation_deadline_ns": profile_deadlines[profile],
                          "round_collection_deadline_ns": deadline, "observation_end_ns": ended,
                          "common_last_speech_seconds": item["common_last_speech_seconds"], "tail_seconds": 15,
                          "role_horizons_ns": {channel: horizons[(profile, channel)] for channel in bindings[profile]},
                          "output_windows_ns": windows,
                          "role_outcomes": role_outcomes,
                          "product_errors": errors[profile], "quiet": quiet,
                          "playback": {channel: {"dac_start_ns": players[key].first_dac_ns,
                                                  "end_ns": players[key].finished_ns, "complete": players[key].done.is_set()}
                                       for channel, (key, _, _) in bindings[profile].items()}}
                failure = errors[profile][0]["reason"] if errors[profile] else None
                self._finish(profile, "product_failure" if failure else "done", failure, detail, outcome)
        except BaseException as error:
            for profile in list(self.open_attempts):
                self._finish(profile, "invalid", "interrupted" if isinstance(error, KeyboardInterrupt) else str(error),
                             {"opportunity_established": False, "continuity_observations": observations.get(profile, [])}, "invalid")
            raise
        finally:
            for player in players.values():
                player.close()
            for task in work:
                profile = task["profile"]
                try:
                    if profile in self.running_profiles:
                        self._stop(profile)
                    self.sink.stop(profile)
                except (OperationalError, ProductError, OSError, ValueError) as error:
                    self.ledger.record("cleanup_failure", {"profile": profile, "error": str(error)})

    def run(self):
        try:
            with exclusive_activity(), RunLock(self.root):
                return self._run()
        finally:
            self.ledger.close()

    def _run(self):
        try:
            self.ledger.seed(self.plan["passes"])
            if self.resume:
                self.ledger.recover()
            self.ledger.record("session_start", {"session": self.session, "resumed": self.resume,
                                                  "synthetic": self.synthetic, "wall": utc_now(),
                                                  "implementation": implementation_provenance()})
            self.sink = NativeSink(self.root, self.plan["run_id"], self.session, self.plan["profiles"])
            if self.resume:
                self._reconcile_capture()
            for execution_round in self.plan["rounds"]:
                work = [task for index in execution_round["pass_indices"] for task in self.ledger.work(index)]
                if all(task["state"] in TERMINAL for task in work):
                    continue
                if self.wave != execution_round["wave"]:
                    self.wave = execution_round["wave"]
                    self.ledger.record("wave_enter", {"wave": self.wave, "profiles": sorted({task["profile"] for task in work}),
                                                       "concurrency": "all first passes concurrent; split B in separate round"})
                self._capture(execution_round)
            return self.ledger.export(self.plan)
        except BaseException as error:
            self.ledger.record("interruption" if isinstance(error, KeyboardInterrupt) else "harness_invalid",
                               {"message": str(error), "type": type(error).__name__, "session": self.session})
            raise
        finally:
            for profile in sorted(set(self.adapters) | self.running_profiles):
                try:
                    if profile in self.running_profiles:
                        self._stop(profile)
                except (OperationalError, ProductError, OSError, ValueError) as error:
                    self.ledger.record("cleanup_failure", {"profile": profile, "error": str(error)})
                if profile in self.adapters:
                    try:
                        path, checksum = self.adapters[profile].close()
                        self.ledger.record("diagnostic_artifact", {"profile": profile, "path": path, "sha256": checksum})
                    except OSError as error:
                        self.ledger.record("cleanup_failure", {"profile": profile, "error": str(error)})
            if self.sink:
                path, checksum = self.sink.close()
                self.ledger.record("stream_artifact", {"path": path, "sha256": checksum})
            self.ledger.record("session_end", {"session": self.session, "wall": utc_now()})
            self.ledger.manifest(self.plan)
