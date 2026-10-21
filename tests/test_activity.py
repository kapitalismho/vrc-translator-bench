from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from bench import activity


@pytest.mark.parametrize("interrupted", [False, True])
def test_activity_excludes_another_process_and_releases(tmp_path, monkeypatch, interrupted):
    path = tmp_path / "activity.lock"
    monkeypatch.setattr(activity, "ACTIVITY_PATH", path)
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from bench import activity\n"
        "activity.ACTIVITY_PATH = Path(sys.argv[1])\n"
        "with activity.exclusive_activity():\n"
        "    print('acquired', flush=True)\n"
        "    sys.stdin.readline()\n"
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(path)],
        cwd=Path(__file__).resolve().parents[1],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        assert child.stdout.readline().strip() == "acquired"
        with pytest.raises(ValueError, match="capture or scoring operation is active"):
            with activity.exclusive_activity():
                pytest.fail("Concurrent operation admitted")
        if interrupted:
            child.kill()
        else:
            child.stdin.write("release\n")
            child.stdin.flush()
        child.communicate(timeout=10)
        with activity.exclusive_activity():
            rejected = subprocess.run(
                [sys.executable, "-c", code, str(path)],
                cwd=Path(__file__).resolve().parents[1],
                input="release\n", capture_output=True, text=True, timeout=10,
            )
            assert rejected.returncode != 0
            assert "capture or scoring operation is active" in rejected.stderr
            assert "acquired" not in rejected.stdout
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)
