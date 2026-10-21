"""Exercise the actual workflow preflight against disposable Git repositories."""
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.mark.skipif(not shutil.which("pwsh"), reason="PowerShell required")
@pytest.mark.parametrize("state", ["clean", "modified", "staged", "untracked", "not_repo"])
def test_nightly_preserves_dirty_evidence(tmp_path, state):
    workflow = Path(__file__).resolve().parents[1] / ".github/workflows/nightly_verify.yml"
    steps = yaml.safe_load(workflow.read_text(encoding="utf-8"))["jobs"]["verify"]["steps"]
    script = next(s["run"] for s in steps if s.get("name") == "Run unified verification suite")
    guard = script.split("python tools/verify_all.py")[0]
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    tracked = tmp_path / "source.txt"
    if state != "not_repo":
        git("init")
        tracked.write_text("original", encoding="utf-8")
        git("add", "source.txt")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
    if state in ("modified", "staged"):
        tracked.write_text("evidence", encoding="utf-8")
        if state == "staged":
            git("add", "source.txt")
    if state == "untracked":
        (tmp_path / "evidence.txt").write_text("preserve", encoding="utf-8")
    result = subprocess.run(["pwsh", "-NoProfile", "-Command", guard], cwd=tmp_path, capture_output=True, text=True)
    assert (result.returncode == 0) == (state == "clean"), result.stdout + result.stderr
    if state in ("modified", "staged"):
        assert tracked.read_text(encoding="utf-8") == "evidence"
    if state == "untracked":
        assert (tmp_path / "evidence.txt").read_text(encoding="utf-8") == "preserve"
