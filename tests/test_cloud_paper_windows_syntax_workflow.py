"""Structural regression: Windows PowerShell compatibility must run on a real Windows CI runner.

This is workflow inspection only; actual execution needs an exact-head Windows Actions receipt.
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "cloud-paper-safety-ci.yml"


def test_cloud_paper_windows_syntax_is_executed_not_ubuntu_skipped():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert "windows-syntax" in jobs, "No dedicated Windows syntax proof job"
    job = jobs["windows-syntax"]
    assert job["runs-on"] == "windows-latest"
    assert job["env"]["PAPER_MODE"] == "1"
    assert job["env"]["LIVE_ORDER_AUTHORITY"] == "0"
    assert job["env"]["REAL_BROKER_ORDERS"] == "0"
    steps = job["steps"]
    text = "\n".join(str(step.get("run", "")) for step in steps)
    assert "git rev-parse HEAD" in text
    assert 'EXPECTED_HEAD_SHA' in text
    assert "test_windows_powershell_syntax" in text
    assert "--junitxml=" in text
    assert "tools/ci_skip_certification_gate.py" in text
    assert any(step.get("if") == "always()" and "ci_skip_certification_gate.py" in str(step.get("run", "")) for step in steps)
    assert not any("continue-on-error" in step for step in steps)
