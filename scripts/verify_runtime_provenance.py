#!/usr/bin/env python3
"""Independent Runtime Provenance Verification Script."""
import json
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import gspread
from google.cloud import bigquery
import credentials

def main():
    creds = credentials.resolve_service_account_info()
    bq = bigquery.Client.from_service_account_info(creds)
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_key("1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs")

    print("=== UNIVERSE & SYMBOL INTEGRITY ===")
    table_id = "fno-angel-prod-1790444589.fno_predictions.option_predictions_live"
    bq_query = f"SELECT symbol, spot_ltp, atm_strike, snapshot_timestamp, run_id, git_sha, writer_id FROM `{table_id}`"
    bq_rows = list(bq.query(bq_query).result())
    bq_symbols = [r["symbol"] for r in bq_rows]
    print(f"BigQuery row count: {len(bq_rows)}")
    print(f"BigQuery unique symbols: {len(set(bq_symbols))}")

    fl = sh.worksheet("FORENSIC_LIVE")
    sheet_rows = fl.get_all_values()
    header = sheet_rows[0]
    sym_idx = header.index("Symbol")
    sheet_symbols = [r[sym_idx] for r in sheet_rows[1:] if r and len(r) > sym_idx and r[sym_idx].strip()]
    print(f"Sheet FORENSIC_LIVE data rows: {len(sheet_symbols)}")
    print(f"Sheet unique symbols: {len(set(sheet_symbols))}")

    manifest = json.loads(open("agent_manifest.json", "r", encoding="utf-8").read())
    manifest_symbols = manifest["universe"]["symbols"]
    print(f"Manifest symbols count: {len(manifest_symbols)}")

    print(f"BigQuery == Manifest: {set(bq_symbols) == set(manifest_symbols)}")
    print(f"Sheet == Manifest: {set(sheet_symbols) == set(manifest_symbols)}")
    print(f"BigQuery == Sheet: {set(bq_symbols) == set(sheet_symbols)}")

    print("\n=== WRITE_PROVENANCE TAB IN GOOGLE SHEET ===")
    wp = sh.worksheet("WRITE_PROVENANCE")
    wp_rows = wp.get_all_values()
    print(f"WRITE_PROVENANCE rows: {len(wp_rows)}")
    for i, r in enumerate(wp_rows[:5]):
        print(f"  Row {i+1}: {r}")

    print("\n=== HEARTBEAT TAB IN GOOGLE SHEET ===")
    hb = sh.worksheet("HEARTBEAT")
    hb_rows = hb.get_all_values()
    for i, r in enumerate(hb_rows[:3]):
        print(f"  Row {i+1}: {r}")

    print("\n=== BIGQUERY TABLES ROW COUNTS ===")
    tables = [
        "option_predictions_live",
        "next_day_gap_predictions",
        "market_news_sentiment",
        "prediction_calibration_log"
    ]
    for tbl in tables:
        t_id = f"fno-angel-prod-1790444589.fno_predictions.{tbl}"
        q = f"SELECT count(*) as cnt FROM `{t_id}`"
        cnt = list(bq.query(q).result())[0]["cnt"]
        print(f"  {tbl}: {cnt} rows")

if __name__ == "__main__":
    main()
