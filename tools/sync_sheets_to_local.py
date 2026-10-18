#!/usr/bin/env python3
r"""
tools/sync_sheets_to_local.py

Enterprise Local Authenticated Bridge for Google Sheets -> Power BI Desktop.
Authenticates via GCP Service Account (angel-sheets-bot) and exports live
worksheets to local CSVs in C:\AngelFNO_Workstation\data\live_sheets\
so Power BI Desktop can refresh locally with zero network authentication errors.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import gspread
import credentials

OUT_DIR = Path(r"C:\AngelFNO_Workstation\data\live_sheets")
TARGET_TABS = [
    "PAPER_ALERT_LOG",
    "NEWS_LIVE",
    "FORENSIC_LIVE",
    "HEARTBEAT",
    "CE_PE_RANK",
    "OPTION_PREDICTIONS",
    "CLOUD_STATUS"
]


def sync_sheets():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting Authenticated Google Sheets Bridge Sync...")
    start_time = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Resolve credentials
    creds_info = credentials.resolve_service_account_info()
    if not creds_info:
        raise RuntimeError("Service account credentials not found in secrets/gcp-service-account.json or environment.")

    # 2. Connect to Google Sheets
    gc = gspread.service_account_from_dict(creds_info)
    sheet_id = credentials.require_authoritative_sheet_id()
    sh = gc.open_by_key(sheet_id)
    print(f"Connected to '{sh.title}' ({sheet_id}) as {creds_info.get('client_email')}")

    available_worksheets = {ws.title: ws for ws in sh.worksheets()}
    synced_tabs = []

    for tab_name in TARGET_TABS:
        if tab_name not in available_worksheets:
            print(f"  [WARN] Tab '{tab_name}' not found in sheet. Skipping.")
            continue

        ws = available_worksheets[tab_name]
        rows = ws.get_all_values()

        if not rows:
            print(f"  [WARN] Tab '{tab_name}' has 0 rows. Skipping.")
            continue

        out_csv = OUT_DIR / f"{tab_name}.csv"
        temp_csv = OUT_DIR / f"{tab_name}.tmp.csv"

        # Sanitize cells (replace any formula error tokens with clean empty strings)
        sanitized_rows = []
        error_tokens = {"#ERROR!", "#REF!", "#NAME?", "#VALUE!", "#N/A", "#DIV/0!"}
        for r in rows:
            sanitized_rows.append([("" if c in error_tokens else c) for c in r])

        # Atomic write to avoid locking conflicts with Power BI Desktop
        with open(temp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(sanitized_rows)

        # Replace destination file atomically
        if out_csv.exists():
            os.replace(temp_csv, out_csv)
        else:
            temp_csv.rename(out_csv)

        print(f"  [SYNCED] {tab_name}.csv -> {len(rows)} rows ({round(out_csv.stat().st_size / 1024, 2)} KB)")
        synced_tabs.append({
            "tab": tab_name,
            "rows": len(rows),
            "columns": len(rows[0]) if rows else 0,
            "size_bytes": out_csv.stat().st_size
        })

    # Save sync metadata
    meta = {
        "synced_at_utc": datetime.now(timezone.utc).isoformat(),
        "synced_at_ist": datetime.now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "sheet_id": sheet_id,
        "spreadsheet_title": sh.title,
        "synced_tabs": synced_tabs,
        "elapsed_seconds": round(time.time() - start_time, 2)
    }

    meta_path = OUT_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as mf:
        json.dump(meta, mf, indent=2)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bridge Sync Completed in {meta['elapsed_seconds']}s! Output: {OUT_DIR}")
    return meta


if __name__ == "__main__":
    try:
        sync_sheets()
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}")
        sys.exit(1)
