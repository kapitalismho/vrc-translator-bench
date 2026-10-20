from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .adapter import Adapter, OperationalError, ProductError, redact
from .audio import ClockPlayback, Playback
from .osc import Sink
from .plan import implementation_provenance, verify_audio
from .storage import Journal, Ledger, RunLock, atomic_json, digest, utc_now


TERMINAL = {"done", "product_failure"}


def speech_timeout(now_ns, dac_start_ns, offset_ns, intervals, last_output_ns):
    elapsed = (now_ns - dac_start_ns - offset_ns) / 1e9
    continuous_start = None
    previous_end = None
    for start, end in intervals:
        if previous_end != start:
            continuous_start = start
        previous_end = end
        if start <= elapsed <= end:
            baseline = dac_start_ns + offset_ns + round(continuous_start * 1e9)
            return now_ns - max(baseline, last_output_ns or baseline) >= 60_000_000_000
    return False


class Runner:
    def __init__(self, root, plan, synthetic=False, resume=False):
        self.root = Path(root)
        self.plan = plan
        self.synthetic = synthetic
        self.resume = resume
        if synthetic != bool(plan.get("synthetic", False)):
            raise OperationalError("Synthetic plans require --audio-backend clock; real plans require wasapi")
        self.session = uuid.uuid4().hex
        self.ledger = Ledger(root)
        self.profiles = {profile["id"]: profile for profile in plan["profiles"]}
        self.adapters = {}
        self.crashed = set()
        self.ready = set()
        self.sink = None
        self.open_attempts = {}
        self.player = None
        self.callback_positions = {}
        self.playback_attempts = {}
        self.wave = None
        self.running_profiles = set()
        self.resume_checked = set()

    def _context(self, stage, attempt):
        return {"wave": stage.get("wave"), "direction": stage.get("direction"),
                "chunk": stage.get("chunk"), "attempt": attempt["id"]}

    def _begin(self, work, stage):
        attempt = self.ledger.begin(work, self.resume)
        journal = Journal(self.root / attempt["trace"])
        self.open_attempts[work["profile"]] = (attempt, journal)
        self.callback_positions[work["profile"]] = 0
        journal.append({"record": "attempt_start", "t_ns": time.perf_counter_ns(), "wall": utc_now(),
                        "run": self.plan["run_id"], "config": work["profile"], "stage": work["stage"],
                        "kind": stage["kind"], "resumed": self.resume, "clock_session": self.session,
                        **self._context(stage, attempt)})
        if self.sink:
            self.sink.attach(work["profile"], self._context(stage, attempt), journal)
        return attempt, journal

    def _save_callbacks(self, profile):
        if self.player is None or profile not in self.open_attempts or self.playback_attempts.get(profile) != self.open_attempts[profile][0]["id"]:
            return
        position = self.callback_positions.get(profile, 0)
        records = self.player.records[position:]
        for record in records:
            self.open_attempts[profile][1].append({"record": "audio_callback", **record})
        self.callback_positions[profile] = position + len(records)

    def _finish(self, profile, state, reason=None, detail=None, outcome=None):
        self._save_callbacks(profile)
        attempt, journal = self.open_attempts.pop(profile)
        if self.sink:
            self.sink.detach(profile)
        journal.append({"record": "attempt_end", "t_ns": time.perf_counter_ns(), "wall": utc_now(),
                        "state": state, "reason": reason, "detail": redact(detail or {})})
        trace, checksum = journal.finalize(".invalid.jsonl" if state == "invalid" else ".jsonl")
        self.ledger.finish(attempt, state, reason, trace, checksum, detail, outcome)
        self.ledger.manifest(self.plan)

    def _adapter(self, profile):
        if profile not in self.adapters:
            self.adapters[profile] = Adapter(self.profiles[profile], self.root, self.session)
        return self.adapters[profile]

    def _expected(self, profile, stage):
        return {**self.profiles[profile]["expected_state"], "direction": stage["direction"]}

    def _claim_capture(self, profile, reason):
        if profile not in self.running_profiles:
            self.running_profiles.add(profile)
            self.ledger.record("capture_ownership", {"profile": profile, "owned": True, "reason": reason,
                                                      "session": self.session, "wave": self.wave})

    def _observe_capture(self, profile, state):
        if state.get("running") is True:
            self._claim_capture(profile, "observed_running")

    def _start(self, profile):
        self._claim_capture(profile, "start_requested")
        if self._adapter(profile).call("start").get("running") is not True:
            raise OperationalError(f"{profile} did not confirm capture running")

    def _reconcile_capture(self):
        owned = sorted(self.ledger.owned_profiles())
        for profile in owned:
            if profile not in self.profiles:
                raise OperationalError(f"Previously owned profile is absent from the frozen plan: {profile}")
            self._claim_capture(profile, "resume_reconciliation")
        for profile in owned:
            state = self._adapter(profile).call("read_state")
            self.ledger.record("capture_reconciliation", {"profile": profile, "state": redact(state),
                                                           "session": self.session})
            if state.get("running") is False:
                self.running_profiles.discard(profile)
                self.ledger.record("capture_ownership", {"profile": profile, "owned": False,
                                                          "reason": "observed_stopped", "session": self.session})
            elif state.get("running") is not True:
                raise OperationalError(f"{profile} reconciliation did not report capture running state")

    def _state(self, profile, stage, correct=False):
        adapter = self._adapter(profile)
        expected = self._expected(profile, stage)
        state = adapter.call("read_state")
        self._observe_capture(profile, state)
        differences = {key: value for key, value in expected.items() if state.get(key) != value}
        corrected = bool(differences) and correct
        if differences and correct:
            adapter.call("configure", requested_state=expected)
            adapter.call("set_direction", direction=stage["direction"])
            state = adapter.call("read_state")
            self._observe_capture(profile, state)
            differences = {key: value for key, value in expected.items() if state.get(key) != value}
        self.ledger.record("application_state", {"profile": profile, "stage": stage["kind"], "state": redact(state),
                                                  "requested": expected, "corrected": corrected})
        if differences:
            raise OperationalError(f"{profile} effective settings mismatch: {sorted(differences)}")
        return state

    def _identity(self, profile):
        identity = self._adapter(profile).call("osc_identity")
        expected_source = self.profiles[profile]["osc"].get("source_port")
        if expected_source is not None and identity.get("source_port") != expected_source:
            raise OperationalError("Adapter source-port identity does not match pinned fallback")
        self.sink.identity(profile, identity)

    def _prepare(self, profile, stage):
        adapter = self._adapter(profile)
        preflight = adapter.call("preflight", profile=self.profiles[profile], direction=stage["direction"])
        self.ledger.record("profile_metadata", {"profile": profile, "direction": stage["direction"],
                                                "metadata": redact(preflight.get("metadata", {}))})
        if preflight.get("supported") is False:
            return False, preflight.get("reason", "unsupported_language")
        if preflight.get("ready") is not True:
            raise OperationalError(f"{profile} preflight not ready: {preflight.get('reason', 'unknown')}")
        state = self._state(profile, stage, correct=True)
        if not state.get("running"):
            self._start(profile)
        running = self._state(profile, stage)
        if running.get("running") is not True:
            raise OperationalError(f"{profile} effective capture is not running")
        self._identity(profile)
        self.ready.add(profile)
        return True, None

    def _unsupported(self, profile, direction, reason):
        if profile in self.open_attempts:
            self._finish(profile, "done", reason, {"supported": False}, outcome="N/A")
        for index, stage in enumerate(self.plan["stages"]):
            if stage["direction"] != direction:
                continue
            for work in self.ledger.work(index):
                if work["profile"] != profile or work["state"] in TERMINAL:
                    continue
                self._begin(work, stage)
                self._finish(profile, "done", reason, {"supported": False}, outcome="N/A")

    def _limit(self, profile, error):
        scope = error.scope or self.profiles[profile].get("quota_scope", profile)
        affected = [identity for identity, spec in self.profiles.items() if identity == profile or spec.get("quota_scope", identity) == scope]
        self.ledger.record("quota_limit", {"profile": profile, "scope": scope, "affected": affected,
                                            "reached_wall": error.reached_wall, "reached_ns": error.reached_ns})
        detail = {"scope": scope, "reached_wall": error.reached_wall,
                  "reached_ns": error.reached_ns, "message": str(error)}
        for identity in list(self.open_attempts):
            if identity in affected:
                self._finish(identity, "product_failure", "limit", detail)
        for index, stage in enumerate(self.plan["stages"]):
            for work in self.ledger.work(index):
                identity = work["profile"]
                if identity not in affected or work["state"] in TERMINAL:
                    continue
                self._begin(work, stage)
                self._finish(identity, "product_failure", "limit", detail)

    def _product(self, profile, error):
        if error.reason == "limit":
            self._limit(profile, error)
            return
        if error.reason == "crash":
            self.crashed.add(profile)
            self.ready.discard(profile)
        self._finish(profile, "product_failure", error.reason, {"message": str(error),
                     "reached_wall": error.reached_wall, "reached_ns": error.reached_ns})

    def _stop(self, profile):
        adapter = self._adapter(profile)
        if adapter.call("stop").get("running") is not False:
            raise OperationalError(f"{profile} did not confirm stopped capture")
        if adapter.call("read_state").get("running") is not False:
            raise OperationalError(f"{profile} effective capture is still running")
        self.running_profiles.discard(profile)
        self.ready.discard(profile)
        self.ledger.record("capture_ownership", {"profile": profile, "owned": False,
                                                  "reason": "confirmed_stop", "session": self.session})

    def _transition(self, stage):
        if self.wave == stage["wave"]:
            return
        target = {profile for item in self.plan["stages"]
                  if item["wave"] == stage["wave"] and item["kind"] not in ("resume_setup", "resume_check")
                  for profile in item["profiles"]}
        for profile in sorted(self.running_profiles - target):
            self._stop(profile)
            self.ledger.record("wave_leave", {"profile": profile, "from_wave": self.wave, "to_wave": stage["wave"]})
        self.ledger.record("wave_enter", {"wave": stage["wave"], "profiles": sorted(target),
                                         "retained": sorted(self.running_profiles & target)})
        self.wave = stage["wave"]

    def _controls(self, index, stage):
        for work in self.ledger.work(index):
            work = next(item for item in self.ledger.work(index) if item["id"] == work["id"])
            if work["state"] in TERMINAL:
                continue
            profile = work["profile"]
            self._begin(work, stage)
            try:
                if stage["kind"] in ("setup", "resume_setup") or profile not in self.ready:
                    supported, reason = self._prepare(profile, stage)
                    if not supported:
                        self._unsupported(profile, stage["direction"], reason)
                        continue
                elif stage["kind"] == "direction":
                    preflight = self._adapter(profile).call("preflight", profile=self.profiles[profile], direction=stage["direction"])
                    if preflight.get("supported") is False:
                        self._unsupported(profile, stage["direction"], preflight.get("reason", "unsupported_language"))
                        continue
                    if preflight.get("ready") is not True:
                        raise OperationalError("Direction preflight is not ready")
                    self._adapter(profile).call("set_direction", direction=stage["direction"])
                    self._state(profile, stage)
                self._finish(profile, "done")
            except ProductError as error:
                self._product(profile, error)
            except (OperationalError, OSError, ValueError) as error:
                self._finish(profile, "invalid", str(error))
                raise OperationalError(str(error)) from error

    def _resume_preparation(self, stage, profiles):
        needed = {profile for profile in profiles if (stage["wave"], profile) not in self.resume_checked}
        if not needed:
            return
        common = {key: stage[key] for key in ("wave", "direction", "chunk")}
        existing = [index for index, item in enumerate(self.plan["stages"])
                    if item["wave"] == stage["wave"] and item["direction"] == stage["direction"]
                    and item["kind"] in ("resume_setup", "resume_check")
                    and any(work["profile"] in needed and work["state"] not in TERMINAL for work in self.ledger.work(index))]
        setups = [index for index in existing if self.plan["stages"][index]["kind"] == "resume_setup"]
        checks = [index for index in existing if self.plan["stages"][index]["kind"] == "resume_check"]
        setup_profiles = {work["profile"] for index in setups for work in self.ledger.work(index) if work["state"] not in TERMINAL}
        check_profiles = {work["profile"] for index in checks for work in self.ledger.work(index) if work["state"] not in TERMINAL}
        if needed - setup_profiles:
            setups.append(len(self.plan["stages"]))
            self.plan["stages"].append({**common, "kind": "resume_setup", "profiles": sorted(needed - setup_profiles)})
        if needed - check_profiles:
            checks.append(len(self.plan["stages"]))
            self.plan["stages"].append({**self.plan["output_check"], **common, "kind": "resume_check",
                                        "profiles": sorted(needed - check_profiles)})
        atomic_json(self.root / "execution-plan.json", self.plan)
        self.ledger.seed(self.plan["stages"])
        for index in setups:
            self._controls(index, self.plan["stages"][index])
        for index in checks:
            self._capture(index, self.plan["stages"][index])
        self.resume_checked.update((stage["wave"], profile) for profile in needed)

    def _capture(self, index, stage):
        work_items = [work for work in self.ledger.work(index) if work["state"] not in TERMINAL]
        if not work_items:
            return
        if self.resume and stage["kind"] not in ("resume_setup", "resume_check"):
            self._resume_preparation(stage, [work["profile"] for work in work_items])
            work_items = [work for work in self.ledger.work(index) if work["state"] not in TERMINAL]
            if not work_items:
                return
        verify_audio(stage)
        active = set()
        for work in work_items:
            work = next(item for item in self.ledger.work(index) if item["id"] == work["id"])
            if work["state"] in TERMINAL:
                continue
            profile = work["profile"]
            self._begin(work, stage)
            try:
                if profile in self.crashed:
                    self._stop(profile)
                    self._start(profile)
                    if self._state(profile, stage, correct=True).get("running") is not True:
                        raise OperationalError("Restart effective capture is not running")
                    self._identity(profile)
                    self.crashed.remove(profile)
                    self.ready.add(profile)
                    self.ledger.record("restart_after_crash", {"profile": profile, "next_chunk": stage["chunk"]})
                elif profile not in self.ready:
                    supported, reason = self._prepare(profile, stage)
                    if not supported:
                        self._unsupported(profile, stage["direction"], reason)
                        continue
                self._state(profile, stage)
                active.add(profile)
            except ProductError as error:
                self._product(profile, error)
            except (OperationalError, OSError, ValueError) as error:
                self._finish(profile, "invalid", str(error))
                raise OperationalError(str(error)) from error
        active.intersection_update(self.open_attempts)
        if not active:
            return
        player = None
        try:
            player = (ClockPlayback if self.synthetic else Playback)(stage["audio"], self.plan.get("output_device"))
            self.player = player
            self.playback_attempts = {profile: self.open_attempts[profile][0]["id"] for profile in active}
            if not self.synthetic:
                calibrated = self.plan["calibration"]["devices"]
                if player.devices["output"][1]["name"] != calibrated["output"][1]["name"]:
                    raise OperationalError("Playback device does not match measured calibration")
            for profile in list(active):
                try:
                    self._adapter(profile).call("begin_stage", stage={**stage, "attempt": self.open_attempts[profile][0]["id"]})
                except ProductError as error:
                    self._product(profile, error)
                    active.discard(profile)
            active.intersection_update(self.open_attempts)
            if not active:
                return
            player.start()
            callback_position = 0
            callback_deadline = time.perf_counter_ns() + 10_000_000_000
            next_liveness = 0
            deadline = None
            while True:
                now = time.perf_counter_ns()
                self.sink.check()
                player.check()
                new_callbacks = player.records[callback_position:]
                for callback in new_callbacks:
                    self.sink.record({"record": "audio_callback", "wave": stage["wave"], "direction": stage["direction"],
                                      "chunk": stage["chunk"], "attempts": self.playback_attempts, **callback})
                callback_position += len(new_callbacks)
                if player.first_dac_ns is None and now >= callback_deadline:
                    raise OperationalError("Playback produced no callback within ten seconds")
                if deadline is not None and player.finished_ns is not None:
                    deadline = max(deadline, player.finished_ns + (self.plan["calibration"]["offset_ns"] or 0) + round(stage["tail_seconds"] * 1e9))
                if player.first_dac_ns is not None and deadline is None:
                    deadline = player.first_dac_ns + (self.plan["calibration"]["offset_ns"] or 0) + round((stage["duration_seconds"] + stage["tail_seconds"]) * 1e9)
                    for profile in list(active):
                        source = {"config": profile, "attempt": self.open_attempts[profile][0]["id"], "chunk": stage["chunk"],
                                  "wave": stage["wave"], "direction": stage["direction"], "clock_session": self.session,
                                  "playback_dac_start_ns": player.first_dac_ns,
                                  "playback_end_ns": player.first_dac_ns + round(stage["duration_seconds"] * 1e9),
                                  "observation_end_ns": deadline, "calibration_offset_ns": self.plan["calibration"]["offset_ns"]}
                        self.sink.source(profile, source)
                        self.open_attempts[profile][1].append({"record": "source_playback", **source,
                                                             "actual_dac_observed": not self.synthetic,
                                                             "audio_sha256": stage["audio_sha256"]})
                for profile in list(active):
                    if profile not in self.open_attempts:
                        active.discard(profile)
                        continue
                    self._save_callbacks(profile)
                    try:
                        self._adapter(profile).observe()
                        if now >= next_liveness:
                            health = self._adapter(profile).call("liveness")
                            if health.get("alive") is False:
                                raise ProductError("crash", "Application process exited")
                            if health.get("alive") is not True:
                                raise OperationalError("Adapter liveness did not confirm alive")
                            if health.get("failure"):
                                failure = health["failure"]
                                raise ProductError(failure["reason"], failure.get("message", ""), failure.get("scope"))
                        if player.first_dac_ns is not None and stage["kind"] not in ("output_check", "resume_check", "nonspeech"):
                            offset = self.plan["calibration"]["offset_ns"] or 0
                            if speech_timeout(now, player.first_dac_ns, offset, stage.get("speech_intervals", []), self.sink.last_output.get(profile)):
                                raise ProductError("no_output", "60 seconds without chatbox output during continuing speech")
                    except ProductError as error:
                        self._product(profile, error)
                        active.discard(profile)
                if now >= next_liveness:
                    next_liveness = now + 1_000_000_000
                if deadline is not None and now >= deadline and player.done.is_set():
                    break
                time.sleep(0.01)
            player.check()
            playback = {"record": "playback", "clock_session": self.session, "actual_dac_observed": not self.synthetic,
                        "dac_start_ns": player.first_dac_ns, "end_ns": player.finished_ns,
                        "calibration": {key: value for key, value in self.plan["calibration"].items()
                                        if key in ("status", "offset_ns", "record_path", "record_sha256", "convention")},
                        "audio_sha256": stage["audio_sha256"]}
            self.sink.record({**playback, "wave": stage["wave"], "direction": stage["direction"],
                              "chunk": stage["chunk"], "attempts": self.playback_attempts,
                              "observation_end_ns": deadline})
            for profile in list(active):
                self.open_attempts[profile][1].append(playback)
                if stage["kind"] in ("output_check", "resume_check") and self.sink.last_output.get(profile) is None:
                    self._finish(profile, "invalid", "output_check_no_output")
                    active.remove(profile)
                    raise OperationalError("Short output check received no nonempty /chatbox/input")
                self._finish(profile, "done")
                active.remove(profile)
        except BaseException as error:
            for profile in list(active):
                if profile in self.open_attempts:
                    if player is not None:
                        self.open_attempts[profile][1].append({"record": "interrupted_playback", "callbacks": player.records,
                                                             "dac_start_ns": player.first_dac_ns, "end_ns": player.finished_ns})
                    self._finish(profile, "invalid", "interrupted" if isinstance(error, KeyboardInterrupt) else str(error))
            raise
        finally:
            if player is not None:
                player.close()
            self.player = None

    def run(self):
        with RunLock(self.root):
            try:
                self.ledger.seed(self.plan["stages"])
                if self.resume:
                    self.ledger.recover()
                self.ledger.record("session_start", {"session": self.session, "resumed": self.resume,
                                                      "synthetic": self.synthetic, "wall": utc_now(),
                                                      "implementation": implementation_provenance()})
                self.sink = Sink(self.root, self.plan["run_id"], self.session, self.plan["profiles"])
                if self.resume:
                    self._reconcile_capture()
                for index, stage in enumerate(self.plan["stages"]):
                    if stage["kind"] in ("resume_setup", "resume_check"):
                        continue
                    if all(work["state"] in TERMINAL for work in self.ledger.work(index)):
                        continue
                    self._transition(stage)
                    if stage["kind"] in ("setup", "direction"):
                        self._controls(index, stage)
                    else:
                        self._capture(index, stage)
                return self.ledger.export(self.plan)
            except BaseException as error:
                self.ledger.record("interruption" if isinstance(error, KeyboardInterrupt) else "harness_invalid",
                                   {"message": str(error), "type": type(error).__name__, "session": self.session})
                for profile in list(self.open_attempts):
                    self._finish(profile, "invalid", "interrupted" if isinstance(error, KeyboardInterrupt) else str(error))
                raise
            finally:
                for profile in sorted(set(self.adapters) | self.running_profiles):
                    try:
                        if profile in self.running_profiles:
                            self._stop(profile)
                    except (OperationalError, ProductError, OSError, ValueError) as error:
                        self.ledger.record("cleanup_failure", {"profile": profile, "error": str(error)})
                    adapter = self.adapters.get(profile)
                    if adapter is None:
                        continue
                    try:
                        path, checksum = adapter.close()
                        self.ledger.record("diagnostic_artifact", {"profile": profile, "path": path, "sha256": checksum})
                    except OSError as error:
                        self.ledger.record("cleanup_failure", {"profile": profile, "error": str(error)})
                if self.sink:
                    path, checksum = self.sink.close()
                    self.ledger.record("stream_artifact", {"path": path, "sha256": checksum})
                self.ledger.record("session_end", {"session": self.session, "wall": utc_now()})
                self.ledger.manifest(self.plan)
                self.ledger.close()
