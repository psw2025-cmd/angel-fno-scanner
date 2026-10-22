"""Regression checks for independently reviewed PR Tests step requirements."""
from copy import deepcopy
import pytest
from tools.ci_evidence_guard import ReceiptError, TRUSTED_REQUIRED_STEPS, verify_ci_receipt

SHA = "a" * 40
REQUIRED = ["pytest"]


def valid_receipt():
    return {
        "head_sha": SHA, "status": "completed", "conclusion": "success",
        "jobs": [{"name": "pytest", "status": "completed", "conclusion": "success",
                  "steps": [{"name": name, "status": "completed", "conclusion": "success"}
                            for name in TRUSTED_REQUIRED_STEPS["pytest"]]}],
    }


def reject(receipt, sha=SHA, jobs=REQUIRED):
    with pytest.raises(ReceiptError):
        verify_ci_receipt(receipt, sha, jobs)


def test_independent_complete_receipt_passes_structural_check_only():
    result = verify_ci_receipt(valid_receipt(), SHA, REQUIRED)
    assert result["status"] == "CI_RECEIPT_STRUCTURAL_CHECK_ONLY"
    assert result["head_sha"] == SHA
    assert "Not authenticated" in result["limitations"]


@pytest.mark.parametrize("field,value", [
    ("head_sha", "b" * 40), ("status", "in_progress"),
    ("conclusion", "failure"), ("conclusion", "skipped"),
    ("jobs", []), ("jobs", None),
])
def test_stale_or_incomplete_run_rejected(field, value):
    receipt = valid_receipt(); receipt[field] = value
    reject(receipt)


@pytest.mark.parametrize("jobs", [[], ["deploy"], ["pytest", "deploy"], ["pytest", "pytest"], None, "pytest"])
def test_caller_cannot_weaken_trusted_job_contract(jobs):
    reject(valid_receipt(), jobs=jobs)


@pytest.mark.parametrize("field,value", [
    ("status", "queued"), ("conclusion", "skipped"),
    ("conclusion", "failure"), ("steps", []), ("steps", None),
])
def test_incomplete_required_job_rejected(field, value):
    receipt = valid_receipt(); receipt["jobs"][0][field] = value
    reject(receipt)


@pytest.mark.parametrize("step_index", [0, 1, 2])
def test_each_mandatory_step_must_be_present(step_index):
    receipt = valid_receipt(); receipt["jobs"][0]["steps"].pop(step_index)
    reject(receipt)


@pytest.mark.parametrize("conclusion", ["skipped", "failure", None])
def test_skipped_failed_or_missing_step_conclusion_rejected(conclusion):
    receipt = valid_receipt(); receipt["jobs"][0]["steps"][0]["conclusion"] = conclusion
    reject(receipt)


def test_self_declared_placeholder_steps_rejected():
    receipt = valid_receipt()
    receipt["jobs"][0]["required_steps"] = ["placeholder"]
    receipt["jobs"][0]["steps"] = [{"name": "placeholder", "status": "completed", "conclusion": "success"}]
    reject(receipt)


def test_self_declared_required_steps_rejected_even_if_correct():
    receipt = valid_receipt()
    receipt["jobs"][0]["required_steps"] = list(TRUSTED_REQUIRED_STEPS["pytest"])
    reject(receipt)


def test_duplicate_required_job_rejected():
    receipt = valid_receipt(); receipt["jobs"].append(deepcopy(receipt["jobs"][0]))
    reject(receipt)


def test_duplicate_required_step_rejected():
    receipt = valid_receipt(); receipt["jobs"][0]["steps"].append(deepcopy(receipt["jobs"][0]["steps"][0]))
    reject(receipt)


def test_extra_failed_job_rejected():
    receipt = valid_receipt(); receipt["jobs"].append({"name": "extra", "status": "completed", "conclusion": "failure"})
    reject(receipt)


def test_missing_required_job_rejected():
    receipt = valid_receipt(); receipt["jobs"][0]["name"] = "other"
    reject(receipt)


def test_invalid_job_shape_rejected():
    receipt = valid_receipt(); receipt["jobs"].append(None)
    reject(receipt)


def test_short_sha_rejected():
    reject(valid_receipt(), sha=SHA[:7])


def test_uppercase_sha_rejected():
    reject(valid_receipt(), sha="A" * 40)


def test_invalid_step_shape_rejected():
    receipt = valid_receipt(); receipt["jobs"][0]["steps"][0] = None
    reject(receipt)
