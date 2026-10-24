"""Structural guard for genuine Windows execution of the PowerShell parser test.

These tests check workflow wiring; only a real Windows Actions job can prove
that the previously skipped test actually ran on the intended commit.
"""
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cloud-paper-safety-ci.yml"


def windows_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    marker = "\n  windows-powershell-syntax:\n"
    assert text.count(marker) == 1, "Dedicated Windows PowerShell gate missing"
    return text.split(marker, 1)[1].split("\n  ", 1)[0]


def test_windows_job_runs_real_previously_skipped_pytest():
    job = windows_job()
    assert "runs-on: windows-latest" in job
    assert "tests/test_infra_readiness.py::test_windows_powershell_syntax" in job
    assert "python -m pytest" in job
    assert "actions/setup-python@v6" in job


def test_windows_job_checks_exact_event_head():
    job = windows_job()
    assert "actions/checkout@v5" in job
    assert "persist-credentials: false" in job
    assert "github.event.pull_request.head.sha || github.sha" in job
    assert "git rev-parse HEAD" in job
    assert "EXPECTED_HEAD_SHA" in job


def test_windows_job_is_mandatory_and_no_secrets():
    job = windows_job()
    assert "continue-on-error:" not in job
    assert "if: false" not in job
    assert "secrets." not in job
    assert "powershell.exe" not in job  # Test itself invokes PowerShell.
