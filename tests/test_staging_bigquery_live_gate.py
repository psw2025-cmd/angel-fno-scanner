"""Offline guards for the read-only staging BigQuery schema check.

These tests use no BigQuery client, network, credentials or live data.
"""
from pathlib import Path

import pytest

from staging_review.live_bigquery_gate import require_live_bigquery_project


EXPECTED = "fno-angel-prod-1790444589"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_project_fails_closed(value):
    env = {} if value is None else {"BQ_PROJECT_ID": value}
    with pytest.raises(RuntimeError, match="BIGQUERY_LIVE_EVIDENCE_BLOCKED"):
        require_live_bigquery_project(env, EXPECTED)


def test_mismatched_project_fails_before_network():
    with pytest.raises(RuntimeError, match="BIGQUERY_PROJECT_MISMATCH"):
        require_live_bigquery_project({"BQ_PROJECT_ID": "other-project"}, EXPECTED)


def test_exact_project_accepted_without_network():
    assert require_live_bigquery_project(
        {"BQ_PROJECT_ID": EXPECTED}, EXPECTED
    ) == EXPECTED


def test_staging_live_check_must_not_skip_missing_evidence():
    source = (Path(__file__).resolve().parents[1] /
              "staging_review" / "test_staging_dry_run.py").read_text(encoding="utf-8")
    assert "pytest.mark.skipif" not in source
    assert "require_live_bigquery_project(os.environ, PROJECT_ID)" in source
