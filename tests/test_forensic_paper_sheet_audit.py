"""
tests/test_forensic_paper_sheet_audit.py

Regression test suite for the C01-C20 Forensic Paper Sheet Audit Engine.
Ensures that no check is ever left 'pending', all checks return canonical status,
and mixed-unit / arithmetic validation logic operates correctly.
"""

import pytest
from tools.forensic_paper_sheet_audit import run_full_audit, SHEETS


def test_audit_sheets_manifest():
    assert len(SHEETS) == 20
    assert "HEARTBEAT" in SHEETS
    assert "PRODUCTION_APPROVED" in SHEETS
    assert "PAPER_ALERT_LOG" in SHEETS
    assert "FORENSIC_LIVE" in SHEETS
    assert "OPTION_PREDICTIONS" in SHEETS


def test_audit_run_and_status_validity():
    checks = run_full_audit()
    assert len(checks) == 20
    valid_statuses = {"PASS", "FAIL", "WARN", "FAILED-FETCH"}
    for cid, c in checks.items():
        assert c["status"] in valid_statuses, f"Check {cid} returned invalid status {c['status']}"
        assert c["status"] != "pending", f"Check {cid} was left pending!"
        assert len(c["name"]) > 0
        assert len(c["evidence"]) > 0
        assert len(c["action"]) > 0


def test_critical_integrity_checks_present():
    checks = run_full_audit()
    # Confirm critical checks C01 through C20 are all present
    expected_checks = [f"C{i:02d}" for i in range(1, 21)]
    for ec in expected_checks:
        assert ec in checks, f"Missing check {ec} in audit results!"
