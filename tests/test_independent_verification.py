"""Negative and positive tests for the independent evidence gate."""
import hashlib
from audit_framework.reconcile import assess

SHA = "a" * 40
DIGEST = hashlib.sha256(b"independent fixture").hexdigest()

def receipt(key="A", status="PASS", **overrides):
    return dict(check_id=key, status=status, source_sha=SHA, run_id="test-run-001", artifact_sha256=DIGEST, **overrides)

def test_two_independent_receipts_pass():
    assert assess([receipt("A"), receipt("B")], ["A", "B"], SHA)["status"] == "PASS"

def test_missing_mandatory_receipt_fails():
    r = assess([receipt()], ["A", "B"], SHA)
    assert r["status"] == "FAIL" and r["gates"]["B"] == "BLOCKED"

def test_internal_failure_even_if_other_receipt_passes():
    assert assess([receipt(), receipt("B", "FAIL")], ["A", "B"], SHA)["status"] == "FAIL"

def test_blocked_cannot_become_green():
    assert assess([receipt("A", "BLOCKED")], ["A"], SHA)["status"] == "FAIL"

def test_conflicting_duplicate_receipts_fail():
    r = assess([receipt(), receipt("A", "FAIL")], ["A"], SHA)
    assert "duplicate_check_id:A" in r["errors"] and r["status"] == "FAIL"

def test_sha_mismatch_fails():
    r = receipt()
    r["source_sha"] = "b" * 40
    assert "invalid_evidence:A" in assess([r], ["A"], SHA)["errors"]

def test_missing_artifact_digest_fails():
    r = receipt()
    r["artifact_sha256"] = ""
    assert assess([r], ["A"], SHA)["status"] == "FAIL"

def test_empty_run_id_fails():
    r = receipt()
    r["run_id"] = ""
    assert assess([r], ["A"], SHA)["status"] == "FAIL"

def test_invalid_expected_sha_fails():
    assert assess([receipt()], ["A"], "not-a-sha")["status"] == "FAIL"

def test_malformed_receipt_fails():
    assert assess([{"check_id": "A"}], ["A"], SHA)["status"] == "FAIL"
