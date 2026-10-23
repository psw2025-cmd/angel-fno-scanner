"""Incident-to-regression tests: optional steps and unreviewed job evidence."""
import pytest
from tools.ci_evidence_guard import verify_ci_receipt, ReceiptError, TRUSTED_REQUIRED_STEPS

SHA = "a" * 40


def receipt():
    return {
        "head_sha": SHA, "status": "completed", "conclusion": "success",
        "jobs": [{
            "name": "pytest", "status": "completed", "conclusion": "success",
            "steps": [
                {"name": name, "status": "completed", "conclusion": "success"}
                for name in TRUSTED_REQUIRED_STEPS["pytest"]
            ],
        }],
    }


@pytest.mark.parametrize("status,conclusion", [
    ("in_progress", "success"), ("queued", "success"), ("completed", None),
    ("completed", "unknown"), ("completed", "failure"), ("completed", "cancelled"),
])
def test_incomplete_or_bad_optional_step_rejected(status, conclusion):
    data = receipt()
    data["jobs"][0]["steps"].append({
        "name": "Optional diagnostic", "status": status, "conclusion": conclusion
    })
    with pytest.raises(ReceiptError):
        verify_ci_receipt(data, SHA, ["pytest"])


@pytest.mark.parametrize("conclusion", ["success", "skipped", "neutral"])
def test_terminal_optional_step_allowed(conclusion):
    data = receipt()
    data["jobs"][0]["steps"].append({
        "name": "Optional diagnostic", "status": "completed", "conclusion": conclusion
    })
    assert verify_ci_receipt(data, SHA, ["pytest"])["status"] == "CI_RECEIPT_STRUCTURAL_CHECK_ONLY"


@pytest.mark.parametrize("steps", [
    None,
    [{"name": "hidden failure", "status": "completed", "conclusion": "failure"}],
    [{"name": "incomplete", "status": "in_progress", "conclusion": None}],
])
def test_unreviewed_extra_successful_job_rejected(steps):
    data = receipt()
    data["jobs"].append({
        "name": "unreviewed", "status": "completed",
        "conclusion": "success", "steps": steps
    })
    with pytest.raises(ReceiptError):
        verify_ci_receipt(data, SHA, ["pytest"])
