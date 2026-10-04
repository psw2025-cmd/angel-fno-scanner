#!/usr/bin/env python3
"""
tools/reconcile_cloud.py

Compare local workstation state vs GitHub origin/main vs BigQuery vs Google Sheet.
Outputs a structured reconciliation table. Exits non-zero on drift.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from angel_prediction_engine import get_bigquery_client, get_gspread_client, SHEET_ID
from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT, verified_symbols

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = "fno_predictions"


def get_git_status():
    local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    try:
        remote_sha = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        remote_sha = "UNKNOWN"
    porcelain = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()
    return {
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "is_synced": local_sha == remote_sha,
        "is_clean": len(porcelain) == 0,
    }


def get_bigquery_state():
    client = get_bigquery_client()
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.option_predictions_live"
    tbl = client.get_table(table_ref)
    run_id_field = next((f for f in tbl.schema if f.name == "run_id"), None)
    return {
        "rows": tbl.num_rows,
        "run_id_type": run_id_field.field_type if run_id_field else "MISSING",
    }


def get_sheet_state():
    gc = get_gspread_client()
    sh = gc.open_by_key(SHEET_ID)
    ws_forensic = sh.worksheet("FORENSIC_LIVE")
    forensic_vals = ws_forensic.get_all_values()
    data_rows = max(0, len(forensic_vals) - 1)

    hb_status = "UNKNOWN"
    try:
        ws_hb = sh.worksheet("HEARTBEAT")
        hb_vals = ws_hb.get_all_values()
        if len(hb_vals) > 1 and len(hb_vals[1]) > 0:
            hb_status = hb_vals[1][0]
    except Exception:
        pass

    return {
        "forensic_symbols": data_rows,
        "heartbeat_status": hb_status,
    }


def main():
    print("=" * 80)
    print(" CLOUD RECONCILIATION AUDIT: Local vs GitHub vs BigQuery vs Google Sheet")
    print("=" * 80)

    drifts = []

    # 1. Manifest
    symbols = verified_symbols()
    manifest_count = len(symbols)
    print(f"\n[1] Canonical Manifest Universe: {manifest_count} symbols (Expected: {EXPECTED_FNO_UNIVERSE_COUNT})")
    if manifest_count != EXPECTED_FNO_UNIVERSE_COUNT:
        drifts.append(f"Manifest symbol count {manifest_count} != expected {EXPECTED_FNO_UNIVERSE_COUNT}")

    # 2. Git
    git_st = get_git_status()
    print(f"\n[2] Git Repository State:")
    print(f"    - Local HEAD SHA : {git_st['local_sha']}")
    print(f"    - Remote main SHA: {git_st['remote_sha']}")
    print(f"    - In Sync with Remote: {git_st['is_synced']}")
    print(f"    - Working Tree Clean : {git_st['is_clean']}")
    if not git_st["is_synced"]:
        drifts.append(f"Git HEAD ({git_st['local_sha'][:10]}) not in sync with origin/main ({git_st['remote_sha'][:10]})")

    # 3. BigQuery
    bq_st = get_bigquery_state()
    print(f"\n[3] BigQuery Sandbox (`option_predictions_live`):")
    print(f"    - Live Snapshot Rows: {bq_st['rows']}")
    print(f"    - run_id Column Type: {bq_st['run_id_type']}")
    if bq_st["rows"] != EXPECTED_FNO_UNIVERSE_COUNT:
        drifts.append(f"BigQuery live rows {bq_st['rows']} != {EXPECTED_FNO_UNIVERSE_COUNT}")
    if bq_st["run_id_type"] != "STRING":
        drifts.append(f"BigQuery run_id type {bq_st['run_id_type']} != STRING")

    # 4. Google Sheet
    sheet_st = get_sheet_state()
    print(f"\n[4] Google Sheet (`OPTION_SHEET`):")
    print(f"    - FORENSIC_LIVE Data Rows: {sheet_st['forensic_symbols']}")
    print(f"    - HEARTBEAT Status Cell   : {sheet_st['heartbeat_status']}")
    if sheet_st["forensic_symbols"] != EXPECTED_FNO_UNIVERSE_COUNT:
        drifts.append(f"Sheet FORENSIC_LIVE rows {sheet_st['forensic_symbols']} != {EXPECTED_FNO_UNIVERSE_COUNT}")

    # Summary
    print("\n" + ("=" * 80))
    print(" RECONCILIATION SUMMARY")
    print("=" * 80)
    print(f"{'Layer':<20} | {'Expected':<15} | {'Observed':<25} | {'Status'}")
    print("-" * 80)
    print(f"{'Manifest':<20} | {EXPECTED_FNO_UNIVERSE_COUNT:<15} | {manifest_count:<25} | {'PASS' if manifest_count == EXPECTED_FNO_UNIVERSE_COUNT else 'DRIFT'}")
    print(f"{'Git Sync':<20} | {'Aligned':<15} | {'Aligned' if git_st['is_synced'] else 'Diverged':<25} | {'PASS' if git_st['is_synced'] else 'DRIFT'}")
    print(f"{'BQ Rows':<20} | {EXPECTED_FNO_UNIVERSE_COUNT:<15} | {bq_st['rows']:<25} | {'PASS' if bq_st['rows'] == EXPECTED_FNO_UNIVERSE_COUNT else 'DRIFT'}")
    print(f"{'BQ run_id Type':<20} | {'STRING':<15} | {bq_st['run_id_type']:<25} | {'PASS' if bq_st['run_id_type'] == 'STRING' else 'DRIFT'}")
    print(f"{'Sheet Symbols':<20} | {EXPECTED_FNO_UNIVERSE_COUNT:<15} | {sheet_st['forensic_symbols']:<25} | {'PASS' if sheet_st['forensic_symbols'] == EXPECTED_FNO_UNIVERSE_COUNT else 'DRIFT'}")
    print("=" * 80)

    if drifts:
        print(f"\n[DRIFT DETECTED] ({len(drifts)} issues found):")
        for d in drifts:
            print(f"  * {d}")
        return 1
    else:
        print("\n[OK] All layers fully reconciled with zero drift.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
