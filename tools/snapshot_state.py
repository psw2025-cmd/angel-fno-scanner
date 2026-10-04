#!/usr/bin/env python3
"""
tools/snapshot_state.py

Capture full system state snapshot to audit/snapshots/<timestamp>.json.
Includes:
- Git SHA, branch, clean/dirty status
- BigQuery schemas, row counts, partitions, and clusters for all four tables
- Infrastructure readiness gate summary
"""
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

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
IST = ZoneInfo("Asia/Kolkata")


def get_git_info():
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    porcelain = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()
    is_clean = len(porcelain) == 0
    return {
        "sha": sha,
        "branch": branch,
        "is_clean": is_clean,
        "uncommitted_changes": porcelain.splitlines() if porcelain else []
    }


def get_bigquery_info():
    client = get_bigquery_client()
    info = {}
    for table_name in TABLES:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"
        try:
            tbl = client.get_table(table_ref)
            part_field = tbl.time_partitioning.field if tbl.time_partitioning else None
            schema_fields = [
                {"name": f.name, "type": f.field_type, "mode": f.mode}
                for f in tbl.schema
            ]
            run_id_field = next((f for f in tbl.schema if f.name == "run_id"), None)
            info[table_name] = {
                "rows": tbl.num_rows,
                "partition_field": part_field,
                "clustering_fields": tbl.clustering_fields,
                "run_id_type": run_id_field.field_type if run_id_field else "MISSING",
                "schema": schema_fields,
            }
        except Exception as e:
            info[table_name] = {"error": str(e)}
    return info


def get_latest_readiness_summary():
    verify_dirs = sorted(Path(r"C:\temp\verify").glob("INFRA_READY_*"), key=lambda p: p.name, reverse=True)
    if not verify_dirs:
        return {"status": "UNKNOWN", "detail": "No previous readiness run found in C:\\temp\\verify"}
    latest_dir = verify_dirs[0]
    status_file = latest_dir / "SYSTEM_STATUS.json"
    if status_file.exists():
        try:
            return json.loads(status_file.read_text(encoding="utf-8"))
        except Exception as e:
            return {"error": str(e)}
    return {"status": "RECORDED", "directory": str(latest_dir)}


def main():
    now_ist = datetime.datetime.now(IST)
    ts_str = now_ist.strftime("%Y%m%d_%H%M%S")
    snapshot_dir = REPO_ROOT / "audit" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = snapshot_dir / f"{ts_str}.json"

    print(f"[INFO] Capturing system state snapshot at {now_ist.isoformat()}...")
    git_info = get_git_info()
    bq_info = get_bigquery_info()
    readiness_info = get_latest_readiness_summary()

    snapshot_data = {
        "timestamp_ist": now_ist.isoformat(),
        "git": git_info,
        "bigquery": bq_info,
        "readiness_probe": readiness_info,
    }

    snapshot_path.write_text(json.dumps(snapshot_data, indent=2, default=str), encoding="utf-8")
    print(f"[OK] State snapshot written to: {snapshot_path}")
    print(f"     Git SHA: {git_info['sha']} ({'clean' if git_info['is_clean'] else 'dirty'})")
    print(f"     BigQuery Tables captured: {len(bq_info)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
