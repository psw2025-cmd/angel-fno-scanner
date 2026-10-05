#!/usr/bin/env python3
"""
staging_review/test_staging_dry_run.py

Dry-run test suite for the staging review components:
1. Tests schema projection pruning extra columns (e.g. cycle_id)
2. Tests provenance retention (run_id, git_sha, writer_id)
3. Tests against live BigQuery table schemas in read-only mode
"""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from staging_review.schema_projection import filter_row_to_table_schema, filter_rows_to_table_schema
from angel_prediction_engine import get_bigquery_client

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = "fno_predictions"


def test_synthetic_projection():
    print("[TEST 1] Testing synthetic schema projection...")
    mock_schema = [
        type("Field", (), {"name": "run_id"})(),
        type("Field", (), {"name": "git_sha"})(),
        type("Field", (), {"name": "writer_id"})(),
        type("Field", (), {"name": "title"})(),
    ]

    test_row = {
        "run_id": "12345",
        "git_sha": "abcdef",
        "writer_id": "market_bot",
        "title": "Nifty rallies 200 pts",
        "cycle_id": "UNEXPECTED_FIELD",  # Extra field that caused 400 error in production
        "extra_random": 999,
    }

    projected = filter_row_to_table_schema(test_row, mock_schema)
    assert "cycle_id" not in projected, "FAIL: cycle_id was not pruned!"
    assert "extra_random" not in projected, "FAIL: extra_random was not pruned!"
    assert projected["run_id"] == "12345", "FAIL: run_id was lost!"
    assert projected["title"] == "Nifty rallies 200 pts", "FAIL: title was lost!"
    print("  [PASS] Synthetic schema projection successfully pruned extra keys while keeping required columns.")


@pytest.mark.skipif(
    not (os.getenv("BQ_PROJECT_ID") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
    reason="Requires live BigQuery credentials; skipped when not configured",
)
def test_live_bigquery_projection():
    print("\n[TEST 2] Testing projection against live BigQuery market_news_sentiment schema...")
    bq = get_bigquery_client()
    table = bq.get_table(f"{PROJECT_ID}.{DATASET_ID}.market_news_sentiment")
    
    test_news_row = {
        "run_id": "37242575613",
        "git_sha": "eaccdaf2e7874c77061fec007980b1c1d13c23c1",
        "writer_id": "market_bot",
        "source_timestamp": "2026-10-05T04:40:47",
        "cycle_id": "20261005_044047",  # This caused the production 400 error
        "symbol": "NIFTY",
        "title": "RBI monetary policy outcome",
        "sentiment": "POSITIVE",
        "non_existent_key": "DROP_ME",
    }

    projected = filter_row_to_table_schema(test_news_row, table)
    # If cycle_id is not yet in the table, it must be safely pruned
    col_names = {f.name for f in table.schema}
    if "cycle_id" not in col_names:
        assert "cycle_id" not in projected, "FAIL: cycle_id should have been pruned from un-migrated table!"
        print("  [PASS] Successfully pruned cycle_id because table lacks column.")
    else:
        assert "cycle_id" in projected, "FAIL: cycle_id should have been kept since column exists!"
        print("  [PASS] Successfully preserved cycle_id because column exists in table.")

    assert "non_existent_key" not in projected
    assert projected["symbol"] == "NIFTY"
    print(f"  [PASS] Filtered from {len(test_news_row)} raw keys down to {len(projected)} valid BigQuery schema keys.")


def main():
    print("=" * 70)
    print(" STAGING REVIEW: DRY-RUN VERIFICATION TEST")
    print("=" * 70)
    test_synthetic_projection()
    test_live_bigquery_projection()
    print("\n" + "=" * 70)
    print(" ALL DRY-RUN CHECKS PASSED (100% SAFE)")
    print("=" * 70)


if __name__ == "__main__":
    main()
