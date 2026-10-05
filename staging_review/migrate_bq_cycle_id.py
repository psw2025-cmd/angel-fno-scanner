#!/usr/bin/env python3
"""
staging_review/migrate_bq_cycle_id.py

Safe, idempotent schema migration script for BigQuery dataset `fno_predictions`.
Ensures that all four production tables have the `cycle_id` STRING column:
- option_predictions_live (already present)
- market_news_sentiment (needs cycle_id)
- next_day_gap_predictions (needs cycle_id)
- prediction_calibration_log (needs cycle_id)

Usage:
    python staging_review/migrate_bq_cycle_id.py          # Dry-run (read-only audit)
    python staging_review/migrate_bq_cycle_id.py --apply  # Execute ALTER TABLE statements
"""
import argparse
import sys
from pathlib import Path

# Add repo root to sys.path
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


def audit_table_columns(bq):
    results = {}
    for table_name in TABLES:
        query = f"""
        SELECT column_name, data_type 
        FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = '{table_name}'
        """
        cols = {r.column_name: r.data_type for r in bq.query(query).result()}
        results[table_name] = cols
    return results


def main():
    parser = argparse.ArgumentParser(description="Audit or apply cycle_id column migration across BigQuery tables.")
    parser.add_argument("--apply", action="store_true", help="Execute the ALTER TABLE statements in BigQuery.")
    args = parser.parse_args()

    bq = get_bigquery_client()
    print("=" * 70)
    print(" BIGQUERY SCHEMA AUDIT: cycle_id Column Verification")
    print(f" Target Dataset: {PROJECT_ID}.{DATASET_ID}")
    print("=" * 70)

    col_map = audit_table_columns(bq)
    missing = []

    for t in TABLES:
        has_cycle_id = "cycle_id" in col_map.get(t, {})
        data_type = col_map.get(t, {}).get("cycle_id", "N/A")
        status = "[PRESENT]" if has_cycle_id else "[MISSING]"
        print(f"  {status:<10} {t:<30} (cycle_id type: {data_type})")
        if not has_cycle_id:
            missing.append(t)

    print("-" * 70)

    if not missing:
        print("[SUCCESS] All 4 BigQuery tables already have cycle_id column. No migration needed.")
        return 0

    print(f"[ACTION REQUIRED] {len(missing)} table(s) lack `cycle_id`: {', '.join(missing)}")

    if not args.apply:
        print("\n[DRY RUN] To apply schema additions safely, re-run with: python staging_review/migrate_bq_cycle_id.py --apply")
        return 0

    print("\n[EXECUTING] Applying schema additions (ALTER TABLE ... ADD COLUMN IF NOT EXISTS)...")
    for t in missing:
        alter_sql = f"""
        ALTER TABLE `{PROJECT_ID}.{DATASET_ID}.{t}`
        ADD COLUMN IF NOT EXISTS cycle_id STRING
        """
        try:
            print(f"  Executing on {t}...")
            job = bq.query(alter_sql)
            job.result()
            print(f"  [OK] Successfully added `cycle_id STRING` to `{t}`.")
        except Exception as e:
            print(f"  [ERROR] Failed to alter `{t}`: {e}", file=sys.stderr)
            return 1

    print("\n[VERIFYING] Re-auditing schemas post-migration...")
    updated_map = audit_table_columns(bq)
    still_missing = [t for t in TABLES if "cycle_id" not in updated_map.get(t, {})]
    if not still_missing:
        print("[SUCCESS] All 4 BigQuery tables now have verified cycle_id STRING column!")
        return 0
    else:
        print(f"[FAIL] Tables still missing cycle_id: {still_missing}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
