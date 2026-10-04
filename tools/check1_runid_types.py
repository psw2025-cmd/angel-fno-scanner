#!/usr/bin/env python3
"""
tools/check1_runid_types.py

Read-only verification of BigQuery run_id column types across all four F&O tables.
Spec requires run_id = STRING (never INT64).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from angel_prediction_engine import get_bigquery_client

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = "fno_predictions"

TABLES = [
    "option_predictions_live",
    "market_news_sentiment",
    "next_day_gap_predictions",
    "prediction_calibration_log",
]


def check_run_id_types():
    client = get_bigquery_client()
    results = {}
    all_ok = True

    print(f"[INFO] Checking run_id column types in BigQuery project '{PROJECT_ID}.{DATASET_ID}'...\n")
    for table_name in TABLES:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        try:
            table = client.get_table(table_ref)
            run_id_field = next((f for f in table.schema if f.name == "run_id"), None)
            field_type = run_id_field.field_type if run_id_field else "MISSING"
        except Exception as e:
            field_type = f"ERROR: {e}"

        is_string = field_type == "STRING"
        status = "[OK]" if is_string else "[FAIL]"
        if not is_string:
            all_ok = False

        results[table_name] = field_type
        print(f"Table: {table_name:<30} | Column: run_id | Type: {field_type:<8} {status}")

    print("\n" + ("=" * 70))
    if all_ok:
        print("[PASS] All four BigQuery run_id columns are STRING.")
        return 0
    else:
        print("[FAIL] One or more BigQuery tables do not have run_id as STRING!")
        return 1


if __name__ == "__main__":
    sys.exit(check_run_id_types())
