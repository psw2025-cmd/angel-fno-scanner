"""Fail-closed infrastructure evidence coverage regressions (offline fixtures only).

These tests do NOT prove authenticated cloud access or PAPER runtime health.
"""
import json

import pytest

from scripts import infra_readiness as infra


CORE = (
    "git_head", "working_tree", "current_main", "219_symbol_config",
    "single_writer_static", "runtime_provenance", "exact_sha_ci",
    "sheet_provenance",
)
ONLINE = CORE + tuple("bq_" + name for name in infra.TABLES)
OFFLINE = CORE + ("bigquery",)


def build_audit(tmp_path, *, mode="VERIFY_ONLY"):
    (tmp_path / "raw").mkdir()
    audit = infra.Audit(tmp_path, tmp_path)
    names = OFFLINE if mode == "OFFLINE" else ONLINE
    for name in names:
        audit.check(name, "NOT_PROVEN" if name == "runtime_provenance" else "PASS",
                    "synthetic metadata-only fixture")
    return audit


def result(tmp_path):
    return json.loads((tmp_path / "SYSTEM_STATUS.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("missing", [
    "git_head", "current_main", "single_writer_static", "exact_sha_ci",
    "sheet_provenance", "bq_option_predictions_live",
])
def test_missing_mandatory_evidence_cannot_be_infrastructure_pass(tmp_path, missing):
    audit = build_audit(tmp_path)
    audit.checks = [c for c in audit.checks if c["check"] != missing]
    assert infra.report(audit, "VERIFY_ONLY") == 1
    status = result(tmp_path)
    assert status["infrastructure"] == "NOT_READY"
    coverage = [c for c in status["checks"] if c["check"] == "evidence_coverage"]
    assert len(coverage) == 1 and coverage[0]["status"] == "FAIL"
    assert missing in coverage[0]["detail"]
    # Every generated human-facing surface must show the failed coverage gate.
    assert "evidence_coverage" in (tmp_path / "SYSTEM_STATUS.html").read_text(encoding="utf-8")


def test_duplicate_required_evidence_cannot_hide_conflicting_observation(tmp_path):
    audit = build_audit(tmp_path)
    audit.check("git_head", "PASS", "duplicate evidence")
    assert infra.report(audit, "VERIFY_ONLY") == 1
    assert "git_head" in next(c["detail"] for c in result(tmp_path)["checks"]
                              if c["check"] == "evidence_coverage")


def test_required_check_marked_not_proven_cannot_be_excluded_from_denominator(tmp_path):
    audit = build_audit(tmp_path)
    next(c for c in audit.checks if c["check"] == "exact_sha_ci")["status"] = "NOT_PROVEN"
    assert infra.report(audit, "VERIFY_ONLY") == 1
    assert result(tmp_path)["infrastructure"] == "NOT_READY"


def test_complete_metadata_contract_still_separates_unproven_runtime(tmp_path):
    audit = build_audit(tmp_path)
    assert infra.report(audit, "VERIFY_ONLY") == 0
    status = result(tmp_path)
    assert status["infrastructure"] == "PASS"
    assert status["runtime"] == "NOT_PROVEN"
    assert next(c for c in status["checks"]
                if c["check"] == "evidence_coverage")["status"] == "PASS"


def test_offline_missing_required_check_never_certifies(tmp_path):
    audit = build_audit(tmp_path, mode="OFFLINE")
    audit.checks = [c for c in audit.checks if c["check"] != "bigquery"]
    assert infra.report(audit, "OFFLINE") == 1
    assert result(tmp_path)["infrastructure"] == "NOT_READY"


def test_unknown_reporting_mode_fails_closed(tmp_path):
    audit = build_audit(tmp_path)
    assert infra.report(audit, "UNRECOGNIZED") == 1
    assert result(tmp_path)["infrastructure"] == "NOT_READY"


def test_blank_check_identity_cannot_be_accepted(tmp_path):
    audit = build_audit(tmp_path)
    audit.check("", "PASS", "blank check name")
    assert infra.report(audit, "VERIFY_ONLY") == 1
    assert result(tmp_path)["infrastructure"] == "NOT_READY"
