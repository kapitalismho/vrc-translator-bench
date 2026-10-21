import json
import socket
from contextlib import ExitStack

import pytest

from bench.profiles import inspect_catalog


@pytest.fixture
def catalog(tmp_path):
    identities = ("PP1", "PP2", "PP3", "PP4", "VRCT1", "VRCT2", "VRCT3", "VRCS1", "VRCS2", "VRCLS1", "KIKI1", "KIKI2", "VRCLT1", "VRCLT2")
    (tmp_path / "procedure.txt").write_text("Synthetic test procedure; not application preparation.", encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps({"synthetic": True}), encoding="utf-8")
    with ExitStack() as stack:
        sockets = [stack.enter_context(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) for _ in range(2 * len(identities))]
        for sock in sockets:
            sock.bind(("127.0.0.1", 0))
        ports = [sock.getsockname()[1] for sock in sockets]
    value = {
        "schema_version": 1,
        "profiles": [{
            "id": identity, "application": f"synthetic-{identity}",
            "finding": "blocked", "reason": "Synthetic contract fixture; no real application observed.",
            "planned": {}, "observed": {},
            "directions": {direction: "source_supported" for direction in ("D1", "D2", "D3", "D4", "D5", "D6")},
            "control": {}, "microphone": {"verified": False},
            "osc": {"host": "127.0.0.1", "send_port": port, "receive_port": control_port},
            "tts": {"verified_off_injection": False}, "updates": {},
            "access": {"exclusive_quota_scope": None},
            "cpu_local": "asr" if identity == "PP4" else None,
            "procedure": "procedure.txt", "evidence": ["evidence.json"], "osc_example": None,
        } for identity, port, control_port in zip(identities, ports[:len(identities)], ports[len(identities):])],
        "waves": [{"id": "paired", "profiles": ["PP4", "VRCT1"]}] + [
            {"id": identity, "profiles": [identity]} for identity in identities if identity not in ("PP4", "VRCT1")
        ],
        "limitations": ["Synthetic validation only; no application readiness evidence."],
    }
    destination = tmp_path / "catalog.json"

    def save():
        destination.write_text(json.dumps(value), encoding="utf-8")
        return destination

    return value, save


def test_source_support_cannot_promote_profile_without_observed_run(catalog):
    value, save = catalog
    profile = value["profiles"][0]
    profile["finding"] = "ready"
    with pytest.raises(ValueError, match="observed route/state"):
        inspect_catalog(save())


def test_manual_osc_is_not_audio_readiness(catalog, tmp_path):
    value, save = catalog
    profile = value["profiles"][0]
    evidence = tmp_path / "observed.json"
    evidence.write_text("{}", encoding="utf-8")
    profile.update(finding="ready", observed={"version": "observed", "asr": "observed", "translation": "observed", "provider_route": "observed", "state_evidence": str(evidence)})
    profile["microphone"]["verified"] = True
    profile["tts"]["verified_off_injection"] = True
    profile["osc_example"] = {"kind": "manual_text_control_probe", "no_vrchat": True, "path": str(evidence)}
    with pytest.raises(ValueError, match="audio-to-OSC"):
        inspect_catalog(save())
    profile["osc_example"]["kind"] = "audio_to_osc"
    profile["directions"]["D1"] = "verified"
    assert inspect_catalog(save())["ready_profiles"] == [profile["id"]]
    profile["observed"]["state_evidence"] = "missing-state.json"
    with pytest.raises(ValueError, match="missing readiness evidence"):
        inspect_catalog(save())
    profile["observed"]["state_evidence"] = str(evidence)
    profile["osc_example"]["path"] = "missing-audio.json"
    with pytest.raises(ValueError, match="missing readiness evidence"):
        inspect_catalog(save())


def test_cpu_local_profiles_cannot_share_wave(catalog):
    value, save = catalog
    by_id = {profile["id"]: profile for profile in value["profiles"]}
    by_id["PP4"]["cpu_local"] = "asr"
    by_id["VRCT1"]["cpu_local"] = None
    assert inspect_catalog(save())["waves"][0]["profiles"] == ["PP4", "VRCT1"]
    by_id["VRCT1"]["cpu_local"] = "translation"
    with pytest.raises(ValueError, match="CPU-local"):
        inspect_catalog(save())
    value["waves"][0]["profiles"] = ["PP4"]
    value["waves"].append({"id": "separate-local", "profiles": ["VRCT1"]})
    assert inspect_catalog(save())["status"] == "blocked"


def test_capture_and_control_ports_cannot_overlap_in_wave(catalog):
    value, save = catalog
    by_id = {profile["id"]: profile for profile in value["profiles"]}
    first, second = "PP4", "VRCT1"
    assert inspect_catalog(save())["waves"][0]["profiles"] == [first, second]
    by_id[second]["osc"]["receive_port"] = by_id[first]["osc"]["send_port"]
    with pytest.raises(ValueError, match="conflicting OSC ports"):
        inspect_catalog(save())
    value["waves"][0]["profiles"] = [first]
    value["waves"].append({"id": "separate-ports", "profiles": [second]})
    assert inspect_catalog(save())["status"] == "blocked"


def test_shared_ip_limited_service_requires_separate_wave(catalog):
    value, save = catalog
    by_id = {profile["id"]: profile for profile in value["profiles"]}
    first, second = "PP4", "VRCT1"
    by_id[first]["access"]["exclusive_quota_scope"] = "service-a"
    by_id[second]["access"]["exclusive_quota_scope"] = "service-b"
    assert inspect_catalog(save())["waves"][0]["profiles"] == [first, second]
    for identity in (first, second):
        by_id[identity]["access"]["exclusive_quota_scope"] = "same-public-ip-service"
    with pytest.raises(ValueError, match="exclusive quota"):
        inspect_catalog(save())
    value["waves"][0]["profiles"] = [first]
    value["waves"].append({"id": "separate-quota", "profiles": [second]})
    assert inspect_catalog(save())["status"] == "blocked"


def test_port_probe_reports_occupied_socket_without_reserving_ports(catalog):
    value, save = catalog
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as occupied:
        port = value["profiles"][0]["osc"]["send_port"]
        occupied.bind(("127.0.0.1", port))
        result = inspect_catalog(save(), check_ports=True)
        assert next(row for row in result["port_observations"] if row["port"] == port)["available"] is False
        assert result["status"] == "blocked"
        available = [row["port"] for row in result["port_observations"] if row["available"]]
        assert available
        for checked_port in available:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as checked:
                checked.bind(("127.0.0.1", checked_port))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as released:
        released.bind(("127.0.0.1", port))
