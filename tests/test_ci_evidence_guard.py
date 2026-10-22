"""CI receipt verification must not accept stale, skipped or partial evidence."""
from copy import deepcopy

import pytest

from tools.ci_evidence_guard import ReceiptError, verify_ci_receipt

SHA = "a" * 40


def valid_receipt():
    return {
        "head_sha": SHA, "status": "completed", "conclusion": "success",
        "jobs": [{
            "name": "pytest", "status": "completed", "conclusion": "success",
            "required_steps": ["Run full pytest"],
            "steps": [{"name": "Run full pytest", "status": "completed", "conclusion": "success"}],
        }],
    }


def test_valid_exact_head_and_required_step_is_accepted():
    result = verify_ci_receipt(valid_receipt(), SHA, ["pytest"])
    assert result["status"] == "CI_RECEIPT_VERIFIED_ONLY"
    assert result["head_sha"] == SHA


@pytest.mark.parametrize("field,value", [
    ("head_sha", "b" * 40),
    ("status", "in_progress"),
    ("conclusion", "failure"),
    ("conclusion", "skipped"),
    ("jobs", []),
    ("jobs", None),
])
def test_incomplete_or_stale_run_rejected(field, value):
    receipt = valid_receipt()
    receipt[field] = value
    with pytest.raises(ReceiptError):
        verify_ci_receipt(receipt, SHA, ["pytest"])


@pytest.mark.parametrize("field,value", [
    ("status", "queued"),
    ("conclusion", "skipped"),
    ("conclusion", "failure"),
    ("required_steps", []),
    ("steps", []),
])
def test_incomplete_job_or_step_evidence_rejected(field, value):
    receipt = valid_receipt()
    receipt["jobs"][0][field] = value
    with pytest.raises(ReceiptError):
        verify_ci_receipt(receipt, SHA, ["pytest"])


def test_duplicate_job_cannot_fake_success():
    receipt = valid_receipt()
    receipt["jobs"].append(deepcopy(receipt["jobs"][0]))
    with pytest.raises(ReceiptError):
        verify_ci_receipt(receipt, SHA, ["pytest"])


def test_skipped_required_step_cannot_fake_success():
    receipt = valid_receipt()
    receipt["jobs"][0]["steps"][0]["conclusion"] = "skipped"
    with pytest.raises(ReceiptError):
        verify_ci_receipt(receipt, SHA, ["pytest"])


def test_missing_required_job_cannot_fake_success():
    with pytest.raises(ReceiptError):
        verify_ci_receipt(valid_receipt(), SHA, ["deploy"])


def test_short_sha_is_not_valid_exact_head():
    with pytest.raises(ReceiptError):
        verify_ci_receipt(valid_receipt(), SHA[:7], ["pytest"])
