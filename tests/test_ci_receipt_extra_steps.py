"""Fail closed on contradictory extra-step evidence without forbidding legitimate optional skips."""
import pytest
from tools.ci_evidence_guard import ReceiptError, TRUSTED_REQUIRED_STEPS, verify_ci_receipt

SHA = "a" * 40


def receipt_with_extra(conclusion, status="completed"):
    steps = [{"name": name, "status": "completed", "conclusion": "success"}
             for name in TRUSTED_REQUIRED_STEPS["pytest"]]
    steps.append({"name": "Run additional audit", "status": status, "conclusion": conclusion})
    return {"head_sha": SHA, "status": "completed", "conclusion": "success",
            "jobs": [{"name": "pytest", "status": "completed", "conclusion": "success",
                      "steps": steps}]}


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "timed_out", "action_required"])
def test_unsuccessful_extra_step_is_not_ignored(conclusion):
    with pytest.raises(ReceiptError, match="Unsuccessful observed step"):
        verify_ci_receipt(receipt_with_extra(conclusion), SHA, ["pytest"])


def test_successful_extra_step_is_allowed():
    assert verify_ci_receipt(receipt_with_extra("success"), SHA, ["pytest"])["status"] == "CI_RECEIPT_STRUCTURAL_CHECK_ONLY"


def test_optional_skipped_extra_step_is_allowed():
    assert verify_ci_receipt(receipt_with_extra("skipped"), SHA, ["pytest"])["status"] == "CI_RECEIPT_STRUCTURAL_CHECK_ONLY"
