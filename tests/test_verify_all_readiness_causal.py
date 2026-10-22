"""Regression: missing readiness evidence must never produce a green audit."""
import json

from tools import verify_all


def _stub_checks(monkeypatch, tmp_path, readiness):
    monkeypatch.setattr(verify_all, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verify_all, "check_git", lambda: {"status": "PASS"})
    monkeypatch.setattr(verify_all, "check_pytest", lambda: {"status": "PASS"})
    monkeypatch.setattr(verify_all, "check_bigquery_types", lambda: {"status": "PASS"})
    monkeypatch.setattr(verify_all, "check_formula_contract", lambda: {"status": "PASS"})
    monkeypatch.setattr(verify_all, "run_readiness_probe", lambda: readiness)


def test_unknown_exact_sha_ci_fails_closed_with_specific_reason(monkeypatch, tmp_path):
    _stub_checks(monkeypatch, tmp_path, {
        "status": "FAIL", "fail_count": 0, "other_count": 2,
        "checks": {"exact_sha_ci": "UNKNOWN", "runtime_provenance": "NOT_PROVEN",
                   "probe_exit_code": 1},
    })
    assert verify_all.main() == 1
    report = json.loads((tmp_path / "audit" / "verify_report.json").read_text())
    assert report["overall_status"] == "FAIL"
    assert any("exact_sha_ci" in reason and "runtime_provenance" in reason
               for reason in report["critical_failures"])
    assert not any("probe_execution" in reason for reason in report["critical_failures"])


def test_missing_probe_evidence_still_fails_closed(monkeypatch, tmp_path):
    _stub_checks(monkeypatch, tmp_path, {
        "status": "FAIL", "fail_count": 1, "other_count": 0,
        "checks": {"probe_execution": "FAIL", "probe_exit_code": 2},
    })
    assert verify_all.main() == 1
    report = json.loads((tmp_path / "audit" / "verify_report.json").read_text())
    assert report["overall_status"] == "FAIL"
    assert any("probe execution" in reason.lower()
               for reason in report["critical_failures"])
