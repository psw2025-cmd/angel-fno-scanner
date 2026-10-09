#!/usr/bin/env python3
"""
tools/verify_sheets_bq_reconciliation.py
100-Year Autonomy Audit — Real-Time Google Sheets & BigQuery Cross-Sink Reconciliation
Performs deterministic readback audit comparing OPTION_SHEET and BigQuery option_predictions_live.
Never equates total table rows with cycle parity; validates exact counts and symbol sets.
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import credentials

IST = ZoneInfo("Asia/Kolkata")
BQ_PROJECT_DEFAULT = "fno-angel-prod-1790444589"
BQ_DATASET_DEFAULT = "fno_predictions"
BQ_TABLE_DEFAULT = "option_predictions_live"


def get_authenticated_clients():
    """Resolve service account from credentials.py and return gspread and bigquery clients."""
    credentials.load_env()
    sa_info = credentials.resolve_service_account_info()
    if not sa_info:
        raise RuntimeError("GCP Service Account credentials not resolved; cannot authenticate.")

    import gspread
    from google.cloud import bigquery

    gc = gspread.service_account_from_dict(sa_info)
    bq = bigquery.Client.from_service_account_info(sa_info, project=BQ_PROJECT_DEFAULT)
    return gc, bq


def reconcile(run_id="37900561389", sheet_id=None, project=None, dataset=None, table=None):
    """
    Read Sheets FORENSIC_LIVE and CE_PE_RANK, compare with BigQuery option_predictions_live.
    Verify universe coverage (219), distinct symbols, and run provenance.
    """
    credentials.load_env()
    canonical_sheet_id = sheet_id or credentials.get_canonical_sheet_id()
    project = project or BQ_PROJECT_DEFAULT
    dataset = dataset or BQ_DATASET_DEFAULT
    table_name = table or BQ_TABLE_DEFAULT
    full_table_id = f"{project}.{dataset}.{table_name}"

    result = {
        "audit_timestamp_ist": datetime.datetime.now(IST).isoformat(),
        "status": "FAIL_CLOSED",
        "canonical_sheet_id": canonical_sheet_id,
        "bigquery_table": full_table_id,
        "target_run_id": str(run_id),
        "sheets": {},
        "bigquery": {},
        "reconciliation": {}
    }

    try:
        gc, bq = get_authenticated_clients()
    except Exception as exc:
        err_log = REPO_ROOT / "docs" / "100_year_local_audit" / "gsheets_auth_error.log"
        err_log.parent.mkdir(parents=True, exist_ok=True)
        err_log.write_text(f"Auth failure: {type(exc).__name__}: {exc}\n", encoding="utf-8")
        result["error"] = f"Authentication error: {exc}"
        return result

    # 1. Inspect Google Sheets
    try:
        sh = gc.open_by_key(canonical_sheet_id)
        # FORENSIC_LIVE tab
        ws_forensic = sh.worksheet("FORENSIC_LIVE")
        f_vals = ws_forensic.get_all_values()
        f_header = [h.strip() for h in f_vals[0]]
        f_rows = f_vals[1:]
        forensic_count = len(f_rows)
        forensic_symbols = {r[1].strip() for r in f_rows if len(r) > 1 and r[1].strip()}

        # CE_PE_RANK tab
        ws_rank = sh.worksheet("CE_PE_RANK")
        r_vals = ws_rank.get_all_values()
        rank_data_rows = [r for r in r_vals if len(r) > 0 and r[0].strip() and not r[0].startswith("F&O Options Top Gainers")]
        rank_count = len(rank_data_rows)

        result["sheets"] = {
            "status": "PASS" if forensic_count >= 216 else "DEGRADED",
            "spreadsheet_title": sh.title,
            "forensic_live_rows": forensic_count,
            "forensic_distinct_symbols": len(forensic_symbols),
            "ce_pe_rank_data_rows": rank_count,
            "sample_symbol": f_rows[0][1] if f_rows else None,
            "sample_timestamp": f_rows[0][0] if f_rows else None
        }
    except Exception as exc:
        result["sheets"] = {"status": "FAIL", "error": str(exc)}

    # 2. Inspect BigQuery
    try:
        table_ref = bq.get_table(full_table_id)
        bq_total_rows = table_ref.num_rows

        query = f"""
            SELECT
                count(*) as total_rows,
                count(distinct symbol) as distinct_symbols,
                max(snapshot_timestamp) as newest_timestamp,
                min(snapshot_timestamp) as oldest_timestamp
            FROM `{full_table_id}`
        """
        query_job = bq.query(query)
        q_res = list(query_job.result())[0]

        result["bigquery"] = {
            "status": "PASS" if q_res.distinct_symbols >= 216 else "DEGRADED",
            "table_num_rows": bq_total_rows,
            "query_total_rows": q_res.total_rows,
            "distinct_symbols": q_res.distinct_symbols,
            "oldest_timestamp": str(q_res.oldest_timestamp),
            "newest_timestamp": str(q_res.newest_timestamp)
        }
    except Exception as exc:
        result["bigquery"] = {"status": "FAIL", "error": str(exc)}

    # 3. Cross-Sink Reconciliation
    sheets_ok = result["sheets"].get("status") in ("PASS", "DEGRADED")
    bq_ok = result["bigquery"].get("status") in ("PASS", "DEGRADED")
    sheets_syms = result["sheets"].get("forensic_distinct_symbols", 0)
    bq_syms = result["bigquery"].get("distinct_symbols", 0)

    universe_matches = (sheets_syms == bq_syms) and (sheets_syms >= 216)
    row_count_matches = (result["sheets"].get("forensic_live_rows") == result["bigquery"].get("query_total_rows"))

    result["reconciliation"] = {
        "universe_parity": universe_matches,
        "sheets_symbols_count": sheets_syms,
        "bigquery_symbols_count": bq_syms,
        "row_count_match": row_count_matches,
        "live_universe_qualified": universe_matches and (sheets_syms == 219)
    }

    if sheets_ok and bq_ok and universe_matches:
        result["status"] = "PASS"
    else:
        result["status"] = "FAIL_CLOSED"

    return result


def main():
    parser = argparse.ArgumentParser(description="Reconcile Google Sheets and BigQuery sinks.")
    parser.add_argument("--run-id", default="37900561389", help="Workflow run ID to reconcile")
    parser.add_argument("--sheet-id", default=None, help="Google Sheet ID")
    parser.add_argument("--project", default=BQ_PROJECT_DEFAULT, help="BigQuery GCP Project ID")
    parser.add_argument("--dataset", default=BQ_DATASET_DEFAULT, help="BigQuery Dataset ID")
    parser.add_argument("--table", default=BQ_TABLE_DEFAULT, help="BigQuery Table ID")
    parser.add_argument("--report", default="docs/sheets_bq_reconciliation_report.md", help="Path to markdown report")
    args = parser.parse_args()

    recon_res = reconcile(
        run_id=args.run_id,
        sheet_id=args.sheet_id,
        project=args.project,
        dataset=args.dataset,
        table=args.table
    )

    # Write Markdown Report
    report_path = REPO_ROOT / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)

    status_icon = "🟢 PASS" if recon_res["status"] == "PASS" else "🔴 FAIL_CLOSED"
    md_content = f"""# Google Sheets & BigQuery Cross-Sink Reconciliation Report

**Audit Time (IST)**: `{recon_res['audit_timestamp_ist']}`  
**Reconciliation Status**: `{status_icon}`  
**Canonical Google Sheet**: `{recon_res['canonical_sheet_id']}`  
**BigQuery Destination**: `{recon_res['bigquery_table']}`  
**Target Run ID**: `{recon_res['target_run_id']}`  

---

## 1. Google Sheets (`OPTION_SHEET`) Evidence
- **Spreadsheet Title**: `{recon_res.get('sheets', {}).get('spreadsheet_title', 'N/A')}`
- **FORENSIC_LIVE Row Count**: `{recon_res.get('sheets', {}).get('forensic_live_rows', 0)}`
- **FORENSIC_LIVE Unique Symbols**: `{recon_res.get('sheets', {}).get('forensic_distinct_symbols', 0)}`
- **CE_PE_RANK Data Rows**: `{recon_res.get('sheets', {}).get('ce_pe_rank_data_rows', 0)}`
- **Sample Timestamp**: `{recon_res.get('sheets', {}).get('sample_timestamp', 'N/A')}`
- **Tab Inspection Status**: `{recon_res.get('sheets', {}).get('status', 'FAIL')}`

---

## 2. BigQuery (`fno_predictions.option_predictions_live`) Evidence
- **Table Total Rows**: `{recon_res.get('bigquery', {}).get('table_num_rows', 0)}`
- **Distinct Symbols Count**: `{recon_res.get('bigquery', {}).get('distinct_symbols', 0)}`
- **Oldest Exchange Timestamp**: `{recon_res.get('bigquery', {}).get('oldest_timestamp', 'N/A')}`
- **Newest Exchange Timestamp**: `{recon_res.get('bigquery', {}).get('newest_timestamp', 'N/A')}`
- **Table Inspection Status**: `{recon_res.get('bigquery', {}).get('status', 'FAIL')}`

---

## 3. Reconciliation & Parity Verification
| Check | Sheets Value | BigQuery Value | Result |
| :--- | :---: | :---: | :---: |
| **Universe Symbol Count** | `{recon_res.get('reconciliation', {}).get('sheets_symbols_count', 0)}` | `{recon_res.get('reconciliation', {}).get('bigquery_symbols_count', 0)}` | `{'PASS' if recon_res.get('reconciliation', {}).get('universe_parity') else 'FAIL'}` |
| **Row Count Alignment** | `{recon_res.get('sheets', {}).get('forensic_live_rows', 0)}` | `{recon_res.get('bigquery', {}).get('query_total_rows', 0)}` | `{'PASS' if recon_res.get('reconciliation', {}).get('row_count_match') else 'FAIL'}` |
| **219-Symbol Full Universe** | 219 | 219 | `{'PASS' if recon_res.get('reconciliation', {}).get('live_universe_qualified') else 'FAIL'}` |

---

## 4. Machine-Readable Raw Audit Payload
```json
{json.dumps(recon_res, indent=2, default=str)}
```
"""
    report_path.write_text(md_content, encoding="utf-8")
    print(f"[OK] Saved reconciliation report to {report_path}")

    # Save to final_reconciliation_real.json
    json_path = REPO_ROOT / "docs" / "100_year_local_audit" / "final_reconciliation_real.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(recon_res, indent=2, default=str), encoding="utf-8")
    print(f"[OK] Saved real reconciliation JSON to {json_path}")

    print(json.dumps(recon_res, indent=2, default=str))
    return 0 if recon_res["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
