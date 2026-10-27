"""CLI data placement and rejection, with synthetic Git metadata and no devices/providers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import bench.cli as cli
import bench.paths as path_module
from bench.paths import DataPathError, DataPaths
from tools import export_pilot_evidence, prepare_ascend, prepare_ingcrowd, prepare_read_controls, prepare_tts


def linked_checkout(primary, linked, identity, *, absolute_gitdir=False):
    linked.mkdir(parents=True)
    gitdir = primary / ".git" / "worktrees" / identity
    gitdir.mkdir(parents=True)
    pointer = str(gitdir) if absolute_gitdir else os.path.relpath(gitdir, linked)
    (linked / ".git").write_text("gitdir: " + pointer + "\n", encoding="utf-8")
    (gitdir / "commondir").write_text("../..\n", encoding="utf-8")
    (gitdir / "gitdir").write_text(os.path.relpath(linked / ".git", gitdir), encoding="utf-8")
    return linked


@pytest.fixture
def checkouts(tmp_path):
    primary = tmp_path / "renamed-primary"
    (primary / ".git").mkdir(parents=True)
    (primary / ".git" / "HEAD").write_text("ref: refs/heads/not-main\n", encoding="utf-8")
    (primary / "bench").mkdir()
    (primary / "bench" / "cli.py").touch()
    (primary / "pyproject.toml").write_text('[project]\nname = "vrc-translator-bench"\n', encoding="utf-8")
    linked = linked_checkout(primary, tmp_path / "arbitrary" / "deep" / "candidate", "opaque-admin-id")
    nested = linked_checkout(primary, primary / ".data" / "worktrees" / "nested", "nested-admin", absolute_gitdir=True)
    return primary, linked, nested


def use_checkout(monkeypatch, checkouts, *, main=False):
    primary, linked, _ = checkouts
    checkout = primary if main else linked
    cwd = checkout / "subdirectory"
    cwd.mkdir(exist_ok=True)
    monkeypatch.chdir(cwd)
    factory = lambda: DataPaths(anchor=checkout / "bench" / "paths.py")
    monkeypatch.setattr(cli, "DataPaths", factory)
    monkeypatch.setattr(path_module, "DataPaths", factory)
    return primary, linked, cwd


@pytest.mark.parametrize("main", [False, True])
@pytest.mark.parametrize("spelling", [".data/results.json", "./.data/results.json", "../.data/results.json"])
def test_primary_and_linked_subdirectory_data_inputs_outputs_agree(checkouts, main, spelling):
    primary, linked, _ = checkouts
    checkout = primary if main else linked
    cwd = checkout / "subdirectory"
    paths = DataPaths(anchor=checkout / "bench" / "paths.py", cwd=cwd)
    expected = primary / ".data" / "results.json"
    assert paths.primary == primary
    assert paths.input(spelling) == expected
    assert paths.output(spelling) == expected
    assert not expected.exists()


def test_absolute_inputs_and_ordinary_relative_inputs_are_not_rewritten(checkouts):
    primary, linked, _ = checkouts
    paths = DataPaths(anchor=linked / "bench" / "paths.py", cwd=linked / "sub")
    absolute_input = linked / ".data" / "retained-manifest.json"
    assert paths.input(absolute_input) == absolute_input
    assert paths.input("../corpus/reference.json") == Path("../corpus/reference.json")
    assert paths.input("cache/.data/model") == Path("cache/.data/model")
    external = primary.parent / "isolated-export" / "report.json"
    assert paths.output(external) == external
    assert paths.output(primary / ".data" / "report.json") == primary / ".data" / "report.json"


@pytest.mark.parametrize("destination", ["absolute", "ordinary-relative", "traversal", "nested"])
def test_linked_outputs_rejected_including_primary_data_nested_worktrees(checkouts, destination):
    primary, linked, nested = checkouts
    paths = DataPaths(anchor=linked / "bench" / "paths.py", cwd=linked / "sub")
    targets = {"absolute": linked / ".data" / "forbidden" / "result.json",
               "ordinary-relative": Path("result.json"),
               "traversal": Path(os.path.relpath(linked / "forbidden", primary)).joinpath("result.json"),
               "nested": Path(".data/worktrees/nested/forbidden/result.json")}
    if destination == "traversal":
        targets[destination] = Path(".data") / ".." / targets[destination]
    with pytest.raises(DataPathError, match="Refusing output inside linked checkout.*primary data path"):
        paths.output(targets[destination])
    assert not (linked / "forbidden").exists()
    assert not (linked / ".data").exists()
    assert not (nested / "forbidden").exists()


def test_loaded_checkout_anchor_wins_and_installed_cwd_requires_harness(checkouts, monkeypatch):
    primary, linked, _ = checkouts
    other = primary.parent / "unrelated"
    (other / ".git").mkdir(parents=True)
    assert DataPaths(anchor=linked / "bench/paths.py", cwd=other).primary == primary
    original = path_module._checkout
    # An installed location has no enclosing checkout, even though the test's
    # isolated files themselves live underneath the developer's primary checkout.
    installed = primary.parent / "installed" / "paths.py"
    monkeypatch.setattr(path_module, "_checkout", lambda path: None if Path(path) == installed else original(path))
    assert DataPaths(anchor=installed, cwd=primary / "bench").primary == primary
    with pytest.raises(DataPathError, match="Cannot identify the primary harness checkout"):
        DataPaths(anchor=installed, cwd=other).output(".data/default.json")
    external = other / "report.json"
    assert DataPaths(anchor=installed, cwd=other).output(external) == external


def test_nonconventional_worktree_layout_fails_without_guessing(checkouts):
    primary, linked, _ = checkouts
    marker = linked / ".git"
    gitdir = (linked / marker.read_text().strip().removeprefix("gitdir: ")).resolve()
    (gitdir / "commondir").write_text("../not-the-common-dir", encoding="utf-8")
    with pytest.raises(DataPathError, match="conventional Git worktree metadata"):
        DataPaths(anchor=linked / "bench/paths.py").output(".data/result.json")


@pytest.mark.parametrize("main", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
def test_bench_default_and_explicit_root_preserves_frozen_plan(checkouts, monkeypatch, main, explicit):
    primary, linked, _ = use_checkout(monkeypatch, checkouts, main=main)
    from test_capture import make_plan
    plan_path = make_plan(primary / ".data/input-bundle", kinds=("P1",))
    expected = cli.load_plan(plan_path, "smoke")
    class Runner:
        def __init__(self, *args):
            pass
        def run(self):
            return {"counts": {"product_failure": 0}}
    monkeypatch.setattr(cli, "Runner", Runner)
    argv = ["run", "--plan", ".data/input-bundle/input-plan.json", "--run-id", "smoke", "--audio-backend", "clock"]
    if explicit:
        argv += ["--root", ".data/runs"]
    assert cli.main(argv) == 0
    for filename in ("frozen-plan.json", "execution-plan.json"):
        assert json.loads((primary / ".data/runs/smoke" / filename).read_text(encoding="utf-8")) == expected
    assert not (linked / ".data").exists()


@pytest.mark.parametrize("command", ["quality", "costs", "calibrate", "playback", "run", "status"])
def test_bench_rejects_before_dispatch_or_files(checkouts, monkeypatch, command, capsys):
    _, linked, _ = use_checkout(monkeypatch, checkouts)
    import bench.quality as quality
    import bench.costs as costs
    def denied(*args, **kwargs):
        pytest.fail("Unsafe output reached file/device/provider dispatch")
    for module, name in [(quality, "evaluate"), (costs, "derive"), (cli, "calibrate"),
                         (cli, "Playback"), (cli, "load_plan"), (cli, "Ledger")]:
        monkeypatch.setattr(module, name, denied)
    target = linked / ".data" / "never-created"
    arguments = {"quality": ["--spec", "missing", "--output", str(target)],
                 "costs": ["--spec", "missing", "--output", str(target)],
                 "calibrate": ["--output", str(target), "--input-device", "unused", "--output-device", "unused"],
                 "playback": ["missing.wav", "--output", str(target), "--output-device", "unused"],
                 "run": ["--plan", "missing", "--root", str(target)],
                 "status": ["missing", "--root", str(target)]}
    assert cli.main([command, *arguments[command]]) == 2
    assert "Refusing output inside linked checkout" in capsys.readouterr().err
    assert not target.parent.exists()


@pytest.mark.parametrize("tool", ["ascend", "controls", "crowd", "asr", "tts-prepare", "tts-generate", "tts-reconcile", "tts-split", "export"])
def test_tools_reject_linked_outputs_before_input_or_provider_work(checkouts, monkeypatch, tool, capsys):
    _, linked, _ = use_checkout(monkeypatch, checkouts)
    def denied(*args, **kwargs):
        pytest.fail("Unsafe output reached materializer/model/credentials/provider/export")
    for module, names in [(prepare_ascend, ["materialize"]), (prepare_read_controls, ["materialize"]),
                          (prepare_ingcrowd, ["materialize", "review_asr"]),
                          (prepare_tts, ["prepare", "generate", "reconcile", "split", "load_key"]),
                          (export_pilot_evidence, ["export"])]:
        for name in names:
            monkeypatch.setattr(module, name, denied)
    output = str(linked / ".data" / "no-files")
    cases = {"ascend": (prepare_ascend, ["--cache", "missing", "--output", output]),
             "controls": (prepare_read_controls, ["--retained", "missing", "--historical-control", "missing", "--output", output]),
             "crowd": (prepare_ingcrowd, ["prepare", "--retained", "missing", "--output", output]),
             "asr": (prepare_ingcrowd, ["asr", "--prepared", "missing", "--model", "missing", "--report", output]),
             "tts-prepare": (prepare_tts, ["prepare", "--scripts", "missing", "--parents", "missing", "--source-cache", "missing", "--output", output]),
             "tts-generate": (prepare_tts, ["generate", "--run", output, "--approval", "missing", "--call", "one", "--env-file", "missing"]),
             "tts-reconcile": (prepare_tts, ["reconcile", "--run", output, "--call", "one", "--env-file", "missing"]),
             "tts-split": (prepare_tts, ["split", "--wav", "missing", "--review", "missing", "--output", output]),
             "export": (export_pilot_evidence, ["--run-directory", "missing", "--output", output])}
    module, argv = cases[tool]
    monkeypatch.setattr(export_pilot_evidence, "DataPaths", path_module.DataPaths)
    if module is prepare_tts:
        assert module.main(argv) == 1
    else:
        with pytest.raises(SystemExit) as error:
            module.main(argv)
        assert error.value.code == 2
    assert "Refusing output inside linked checkout" in capsys.readouterr().err
    assert not (linked / ".data").exists()


@pytest.mark.parametrize("adapter", ["gui", "kikitan"])
def test_adapter_rejects_linked_directory_before_construction(checkouts, monkeypatch, adapter, capsys):
    _, linked, _ = use_checkout(monkeypatch, checkouts)
    from bench import gui_operator_adapter, kikitan_adapter
    module = gui_operator_adapter if adapter == "gui" else kikitan_adapter
    monkeypatch.setattr(module, "DataPaths", path_module.DataPaths)
    def denied(*args, **kwargs):
        pytest.fail("Unsafe output reached adapter construction")
    monkeypatch.setattr(module, "GuiOperator" if adapter == "gui" else "KikitanController", denied)
    argv = ["--directory", str(linked / ".data/unsafe"), "--profile", "KIKI2"]
    argv += ["--owned-pid", "123", "--session", "one"] if adapter == "gui" else ["--executable", "unused"]
    with pytest.raises(SystemExit) as error:
        module.main(argv)
    assert error.value.code == 2
    assert "Refusing output inside linked checkout" in capsys.readouterr().err
    assert not (linked / ".data").exists()


def test_artifact_relative_audio_resolution_is_not_rebased(checkouts, monkeypatch):
    primary, linked, _ = use_checkout(monkeypatch, checkouts)
    from test_capture import make_plan
    from bench.plan import load_plan
    directory = primary / ".data" / "input-bundle"
    plan_path = make_plan(directory, kinds=("P1",))
    record = json.loads(plan_path.read_text(encoding="utf-8"))
    audio = Path(record["episodes"][0]["roles"]["A"]["audio"])
    record["episodes"][0]["roles"]["A"]["audio"] = audio.name
    plan_path.write_text(json.dumps(record), encoding="utf-8")
    original = plan_path.read_bytes()
    selected = DataPaths(anchor=linked / "bench/paths.py").input(".data/input-bundle/input-plan.json")
    plan = load_plan(selected, "smoke")
    assert plan["episodes"][0]["roles"]["A"]["audio"] == str(audio)
    assert plan_path.read_bytes() == original


@pytest.mark.parametrize("script", ["prepare_ascend.py", "prepare_ingcrowd.py", "prepare_read_controls.py", "prepare_tts.py", "export_pilot_evidence.py"])
def test_direct_tool_script_imports_without_editable_install(script, tmp_path, checkouts):
    repository = Path(cli.__file__).resolve().parents[1]
    _, linked, _ = checkouts
    target = linked / ".data" / "forbidden"
    arguments = {
        "prepare_ascend.py": ["--cache", "missing", "--output", str(target)],
        "prepare_ingcrowd.py": ["prepare", "--retained", "missing", "--output", str(target)],
        "prepare_read_controls.py": ["--retained", "missing", "--historical-control", "missing", "--output", str(target)],
        "prepare_tts.py": ["split", "--wav", "missing", "--review", "missing", "--output", str(target)],
        "export_pilot_evidence.py": ["--run-directory", "missing", "--output", str(target)],
    }
    environment = {**os.environ, "PYTHONPATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-S", "-B", str(repository / "tools" / script), *arguments[script]],
                            cwd=tmp_path, env=environment, text=True, capture_output=True, timeout=20)
    assert result.returncode == (1 if script == "prepare_tts.py" else 2), result.stderr
    assert "Refusing output inside linked checkout" in result.stderr
    assert "Traceback" not in result.stderr
    assert not target.parent.exists()
