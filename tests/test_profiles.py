import copy
import json
import socket
from pathlib import Path

import pytest

from bench.profiles import inspect_catalog


CATALOG = Path(__file__).resolve().parents[1] / "profiles" / "catalog.json"
EXPECTED_WAVES = {
    "W1": ["PP4", "KIKI2", "VRCLT1", "VRCT3"],
    "W2": ["VRCT1", "PP1", "VRCS2", "KIKI1"],
    "W3": ["VRCT2", "VRCLT2", "PP2"],
    "W4": ["VRCS1", "PP3", "VRCLS1"],
}
SCOPES = ["ordinary/en-zh", "ordinary/ja-ko", "t1/en-zh/A", "t1/en-zh/B", "t1/ja-ko/A", "t1/ja-ko/B"]


@pytest.fixture
def catalog(tmp_path):
    value = json.loads(CATALOG.read_text(encoding="utf-8"))
    for profile in value["profiles"]:
        profile["procedure"] = str((CATALOG.parent / profile["procedure"]).resolve())
        profile["evidence"] = [str((CATALOG.parent / name).resolve()) for name in profile["evidence"]]
        # Mutation cases start unverified; maintained real evidence is checked below.
        profile["native_protocol"]["early_feasibility"] = {"confirmed": [], "blockers": [], "unverified": list(SCOPES)}
    destination = tmp_path / "catalog.json"

    def save():
        destination.write_text(json.dumps(value), encoding="utf-8")
        return destination

    return value, save


def profile(value, identity):
    return next(row for row in value["profiles"] if row["id"] == identity)


def confirm(tmp_path, row, scope="ordinary/en-zh"):
    """Synthetic validator input only; never written into the maintained catalog."""
    native = row["native_protocol"]
    evidence = {
        "protocol": "native-output-v1", "profile": row["id"], "scope": scope,
        "kind": "input_to_native_translation", "condition": copy.deepcopy(native["condition"]),
        "endpoint": copy.deepcopy(native["endpoint"]),
        "models": {key: row["planned"][key] for key in ("asr", "translation")},
        "app_version": "synthetic-test-build", "instance": "synthetic-test-instance",
        "translated_text": "Synthetic translation, not an observed app result.",
    }
    if "peer_asr" in native:
        evidence["peer_asr"] = native["peer_asr"]
    for key in ("input_evidence", "raw_evidence", "clock_evidence"):
        name = f"{row['id']}-{key}.json"
        (tmp_path / name).write_text('{"synthetic": true}', encoding="utf-8")
        evidence[key] = name
    name = f"{row['id']}-confirmation.json"
    native["early_feasibility"]["confirmed"].append({"scope": scope, "evidence": name})
    native["early_feasibility"]["unverified"].remove(scope)

    def save_evidence():
        (tmp_path / name).write_text(json.dumps(evidence), encoding="utf-8")

    save_evidence()
    return evidence, save_evidence


def test_maintained_catalog_preserves_inventory_waves_and_condition_contract():
    result = inspect_catalog(CATALOG)
    assert {wave["id"]: wave["profiles"] for wave in result["waves"]} == EXPECTED_WAVES
    assert {row["id"] for row in result["findings"]} == {identity for members in EXPECTED_WAVES.values() for identity in members}
    for row in result["findings"]:
        assert row["final_admission"] == {"owner": "R6", "quality": "pending_r6", "time": "pending_r6"}
        condition = row["condition"]
        split = row["id"] in ("VRCLT1", "VRCLT2", "KIKI1", "KIKI2")
        assert condition["ordinary_input"] == ("self" if split else "peer")
        assert condition["t1_mode"] == ("split_self" if split else "simultaneous")
        assert condition["roles"] == {"A": "self" if split else "peer", "B": "self"}
        assert condition["t1_directions"] == {"A": ["en->zh", "ja->ko"], "B": ["zh->en", "ko->ja"]}


def test_old_ready_and_direction_fields_are_history_not_an_alternate_evaluator(catalog):
    value, save = catalog
    row = profile(value, "PP1")
    row.update(finding="ready", directions={}, observed={}, osc_example=None)
    assert inspect_catalog(save())["new_protocol_status"] == "unverified"


@pytest.mark.parametrize("change", ("missing", "duplicate", "foreign"))
def test_inventory_cannot_shrink_or_duplicate(catalog, change):
    value, save = catalog
    if change == "missing":
        value["profiles"].pop()
    elif change == "duplicate":
        value["profiles"].append(copy.deepcopy(value["profiles"][0]))
    else:
        value["profiles"][0]["id"] = "PP5"
    with pytest.raises(ValueError, match="profile"):
        inspect_catalog(save())


@pytest.mark.parametrize("identity,field,replacement", [
    ("PP4", "asr", "Gemini 3.5 Transcribe"),
    ("PP2", "translation", "GPT 6 Luna / paid API"),
    ("VRCLT2", "translation", "Gemini Live Translate 3.5"),
    ("KIKI1", "asr", "Whisper base"),
])
def test_model_comparison_cannot_be_silently_substituted(catalog, identity, field, replacement):
    value, save = catalog
    profile(value, identity)["planned"][field] = replacement
    with pytest.raises(ValueError, match="model comparison"):
        inspect_catalog(save())


def test_profile_family_and_separate_peer_asr_are_enforced(catalog):
    value, save = catalog
    row = profile(value, "PP4")
    row["application"] = "VRCS"
    with pytest.raises(ValueError, match="family"):
        inspect_catalog(save())
    row["application"] = "PuriPuly"
    row["native_protocol"]["peer_asr"] = "gemini_transcribe"
    with pytest.raises(ValueError, match="peer ASR"):
        inspect_catalog(save())


@pytest.mark.parametrize("identity,key,replacement", [
    ("KIKI1", "ordinary_input", "peer"), ("VRCLT2", "t1_mode", "simultaneous"),
    ("VRCS1", "t1_mode", "split_self"), ("VRCT1", "roles", {"A": "self", "B": "peer"}),
    ("KIKI2", "ordinary_directions", ["zh->en", "ko->ja"]),
    ("PP1", "vrchat", "required"),
])
def test_condition_role_and_language_cannot_drift(catalog, identity, key, replacement):
    value, save = catalog
    profile(value, identity)["native_protocol"]["condition"][key] = replacement
    with pytest.raises(ValueError, match="condition/role/direction"):
        inspect_catalog(save())


@pytest.mark.parametrize("change", ("drop", "repeat", "old_direction", "ready_flag"))
def test_all_native_scopes_need_explicit_nonconflicting_states(catalog, change):
    value, save = catalog
    early = profile(value, "PP1")["native_protocol"]["early_feasibility"]
    if change == "drop":
        early["unverified"].pop()
    elif change == "repeat":
        early["unverified"][-1] = early["unverified"][0]
    elif change == "old_direction":
        early["unverified"][-1] = "D1"
    else:
        early["ready"] = True
    with pytest.raises(ValueError, match="scope|states"):
        inspect_catalog(save())


@pytest.mark.parametrize("field", ("quality", "time"))
def test_r1_cannot_grant_final_admission(catalog, field):
    value, save = catalog
    profile(value, "PP1")["native_protocol"]["final_admission"][field] = "admitted"
    with pytest.raises(ValueError, match="pending R6"):
        inspect_catalog(save())


def test_individual_confirmation_never_promotes_sibling_or_final_admission(catalog, tmp_path):
    value, save = catalog
    confirm(tmp_path, profile(value, "PP1"))
    result = inspect_catalog(save())
    assert result["new_protocol_status"] == "partially_confirmed"
    rows = {row["id"]: row for row in result["findings"]}
    assert len(rows["PP1"]["early_feasibility"]["confirmed"]) == 1
    assert rows["PP2"]["early_feasibility"]["confirmed"] == []
    assert rows["PP1"]["final_admission"]["quality"] == "pending_r6"
    assert result["final_admission"]["time"] == "pending_r6"


@pytest.mark.parametrize("field,bad", [
    ("protocol", "historical-self-osc"), ("profile", "PP2"), ("scope", "t1/en-zh/A"),
    ("kind", "manual_text_control_probe"), ("condition", {}), ("models", {}),
    ("endpoint", {}), ("peer_asr", "local_cpu_auto"), ("translated_text", ""),
    ("instance", ""), ("raw_evidence", "missing.json"), ("input_evidence", "missing.json"),
    ("clock_evidence", "missing.json"),
])
def test_confirmation_requires_profile_scope_model_route_and_actual_evidence(catalog, tmp_path, field, bad):
    value, save = catalog
    evidence, save_evidence = confirm(tmp_path, profile(value, "PP1"))
    evidence[field] = bad
    save_evidence()
    with pytest.raises(ValueError, match="evidence|confirmation"):
        inspect_catalog(save())


def test_vrct_cannot_confirm_received_without_independent_ocr_off_proof(catalog, tmp_path):
    value, save = catalog
    evidence, save_evidence = confirm(tmp_path, profile(value, "VRCT1"))
    with pytest.raises(ValueError, match="OCR"):
        inspect_catalog(save())
    evidence.update(ocr_disabled=True, external_text_disabled=True, ocr_evidence="ocr-off.json")
    save_evidence()
    with pytest.raises(ValueError, match="ocr-off"):
        inspect_catalog(save())
    (tmp_path / "ocr-off.json").write_text('{"synthetic": true}', encoding="utf-8")
    assert inspect_catalog(save())["new_protocol_status"] == "partially_confirmed"


def test_blockers_remain_scoped_and_cannot_coexist_with_same_scope_confirmation(catalog, tmp_path):
    value, save = catalog
    row = profile(value, "PP1")
    early = row["native_protocol"]["early_feasibility"]
    early["blockers"] = [{"scope": "t1/ja-ko/B", "reason": "Synthetic missing reverse input."}]
    confirm(tmp_path, row)
    assert inspect_catalog(save())["new_protocol_status"] == "partially_confirmed"
    early["blockers"][0]["scope"] = "all"
    with pytest.raises(ValueError, match="unresolved blocker"):
        inspect_catalog(save())


@pytest.mark.parametrize("change", ("serialize", "swap", "missing", "duplicate"))
def test_exact_concurrent_waves_cannot_be_replanned(catalog, change):
    value, save = catalog
    if change == "serialize":
        value["waves"][0]["profiles"].pop()
    elif change == "swap":
        value["waves"][0]["profiles"][0], value["waves"][1]["profiles"][0] = value["waves"][1]["profiles"][0], value["waves"][0]["profiles"][0]
    elif change == "missing":
        value["waves"].pop()
    else:
        value["waves"].append(copy.deepcopy(value["waves"][0]))
    with pytest.raises(ValueError, match="W1-W4"):
        inspect_catalog(save())


def test_cpu_conditions_and_exclusive_quota_conflicts_are_not_hidden(catalog):
    value, save = catalog
    row = profile(value, "VRCT3")
    row["cpu_local"] = "translation"
    with pytest.raises(ValueError, match="competing CPU-local"):
        inspect_catalog(save())
    row["cpu_local"] = None
    profile(value, "PP4")["cpu_local"] = None
    with pytest.raises(ValueError, match="CPU-local model"):
        inspect_catalog(save())
    profile(value, "PP4")["cpu_local"] = "asr"
    profile(value, "PP4")["access"]["exclusive_quota_scope"] = "shared"
    row["access"]["exclusive_quota_scope"] = "shared"
    with pytest.raises(ValueError, match="exclusive quota"):
        inspect_catalog(save())


@pytest.mark.parametrize("port", (0, -1, 65536, True, "2231", None))
def test_native_network_ports_reject_invalid_boundaries(catalog, port):
    value, save = catalog
    profile(value, "VRCT1")["native_protocol"]["endpoint"]["port"] = port
    with pytest.raises(ValueError, match="native port"):
        inspect_catalog(save())


@pytest.mark.parametrize("port", (1, 65535))
def test_native_port_boundaries_are_valid_without_binding_privileged_ports(catalog, port):
    value, save = catalog
    profile(value, "VRCT1")["native_protocol"]["endpoint"]["port"] = port
    assert inspect_catalog(save())["new_protocol_status"] == "unverified"


@pytest.mark.parametrize("identity,key,bad", [
    ("KIKI1", "port", 19151), ("KIKI2", "path", "/desktop/translated"),
    ("VRCT1", "host", "0.0.0.0"), ("VRCS1", "path", "/v1/internal"),
    ("VRCLS1", "transport", "osc"),
])
def test_family_native_channel_and_local_boundary_are_enforced(catalog, identity, key, bad):
    value, save = catalog
    profile(value, identity)["native_protocol"]["endpoint"][key] = bad
    with pytest.raises(ValueError, match="native endpoint|native port"):
        inspect_catalog(save())


def test_native_port_conflicts_are_transport_specific_and_wave_local(catalog):
    value, save = catalog
    # W2 hosts both VRCS and VRCT; TCP bind conflicts cannot be concealed by distinct apps.
    profile(value, "VRCS2")["native_protocol"]["endpoint"]["port"] = 2231
    with pytest.raises(ValueError, match="conflicting native ports"):
        inspect_catalog(save())
    profile(value, "VRCS2")["native_protocol"]["endpoint"]["port"] = 18378
    with pytest.raises(ValueError, match="conflicting native ports"):
        inspect_catalog(save())
    profile(value, "VRCS2")["native_protocol"]["endpoint"]["port"] = 19131
    # TCP 19131 and VRCLT UDP 19131 are distinct. KIKI1/2 reuse TCP18378
    # only in separate fixed waves.
    assert inspect_catalog(save())["new_protocol_status"] == "unverified"


def test_probes_inspect_native_tcp_udp_only_and_release_all_sockets(catalog):
    value, save = catalog
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        profile(value, "VRCT1")["native_protocol"]["endpoint"]["port"] = port
        result = inspect_catalog(save(), check_ports=True)
        observations = result["port_observations"]
        assert next(row for row in observations if (row["transport"], row["port"]) == ("tcp", port))["available"] is False
        assert result["new_protocol_status"] == "unverified"
        assert ("tcp", 18378) in {(row["transport"], row["port"]) for row in observations}
        assert ("udp", 19104) not in {(row["transport"], row["port"]) for row in observations}
        for row in observations:
            if row["available"]:
                kind = socket.SOCK_STREAM if row["transport"] == "tcp" else socket.SOCK_DGRAM
                with socket.socket(socket.AF_INET, kind) as released:
                    released.bind(("127.0.0.1", row["port"]))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as released:
        released.bind(("127.0.0.1", port))
