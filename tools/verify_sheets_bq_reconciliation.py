"""Authenticated read-only sink inspection. Never equate total table rows with cycle parity."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
IST=ZoneInfo("Asia/Kolkata")

def inspect(run_id, expected_sha, *, project=None, table=None, sheet_id=None):
    from angel_prediction_engine import get_bigquery_client, get_gspread_client, SHEET_ID
    from google.cloud import bigquery
    result={"status":"FAIL_CLOSED","expected_run_id":str(run_id),
            "expected_git_sha":str(expected_sha),"sheets":"NOT_VERIFIED","bigquery":"NOT_VERIFIED"}
    gc=get_gspread_client()
    sh=gc.open_by_key(sheet_id or SHEET_ID)
    sheets={}
    for tab in ("FORENSIC_LIVE","CE_PE_RANK"):
        vals=sh.worksheet(tab).get_all_values()
        if not vals:raise ValueError(f"{tab} has no headers")
        headers=[v.strip().lower() for v in vals[0]]
        if len(headers)!=len(set(headers)):raise ValueError(f"{tab} duplicate headers")
        rows=[dict(zip(headers,r+[""]*(len(headers)-len(r)))) for r in vals[1:] if any(v.strip() for v in r)]
        sheets[tab]={"rows":len(rows),"headers":headers}
        target=219 if tab=="FORENSIC_LIVE" else 200
        if len(rows)!=target:raise ValueError(f"{tab} rows {len(rows)} != {target}")
        run_field=next((x for x in ("run_id","source_run_id","publication_run_id") if x in headers),None)
        if not run_field:raise ValueError(f"{tab} lacks run_id provenance column")
        if any(str(r[run_field]).strip()!=str(run_id) for r in rows):
            raise ValueError(f"{tab} run_id differs from requested production run")
        symbol_field=next((x for x in ("symbol","tradingsymbol","ticker") if x in headers),None)
        if not symbol_field or len({r[symbol_field].strip() for r in rows})!=target:
            raise ValueError(f"{tab} symbol identity/uniqueness mismatch")
    result["sheets"]={"status":"PASS","tabs":sheets}
    bq=get_bigquery_client()
    project=project or os.environ.get("BQ_PROJECT_ID")
    table=table or os.environ.get("BQ_TABLE","fno_predictions.option_predictions_live")
    if not project:raise ValueError("BQ_PROJECT_ID required")
    table_id=f"{project}.{table}"
    schema={f.name:f.field_type for f in bq.get_table(table_id).schema}
    for field in ("run_id","symbol","exchange_timestamp"):
        if field not in schema:raise ValueError(f"BQ missing {field}")
    if schema["run_id"]!="STRING":raise ValueError("BQ run_id not STRING")
    query=f"""SELECT COUNT(*) AS rows, COUNT(DISTINCT symbol) AS symbols,
             MIN(exchange_timestamp) AS oldest, MAX(exchange_timestamp) AS newest
             FROM `{table_id}`
             WHERE run_id=@run_id
             AND DATE(exchange_timestamp,'Asia/Kolkata')=@market_date"""
    date=datetime.now(IST).date()
    cfg=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("run_id","STRING",str(run_id)),
        bigquery.ScalarQueryParameter("market_date","DATE",date)])
    row=next(iter(bq.query(query,job_config=cfg).result()))
    result["bigquery"]={"rows":row.rows,"symbols":row.symbols,"oldest":str(row.oldest),
                         "newest":str(row.newest),"market_date":str(date)}
    if row.rows!=219 or row.symbols!=219:raise ValueError("BQ expected 219 distinct rows for run/date")
    result["bigquery"]["status"]="PASS"
    result["status"]="PASS_COUNTS_ONLY"
    result["warning"]="Cross-sink row checksum and identical exchange timestamp proof not yet implemented"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--run-id",default="37900561389")
    p.add_argument("--sha",default="8c7862b")
    p.add_argument("--project")
    p.add_argument("--table")
    p.add_argument("--sheet-id")
    p.add_argument("--report",default="docs/sheets_bq_reconciliation_report.md")
    a=p.parse_args()
    try:r=inspect(a.run_id,a.sha,project=a.project,table=a.table,sheet_id=a.sheet_id)
    except Exception as e:r={"status":"FAIL_CLOSED","reason":f"{type(e).__name__}: external readback failed; see authenticated client logs",
                              "run_id":a.run_id,"sheets":"NOT_VERIFIED_OR_PARTIAL",
                              "bigquery":"NOT_VERIFIED_OR_PARTIAL"}
    report=Path(a.report)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text("# Sheets / BigQuery independent reconciliation\n\n"+
                      "Read-only audit. No inferred production success.\n\n"+
                      "```json\n"+json.dumps(r,indent=2,default=str)+"\n```\n",encoding="utf-8")
    print(json.dumps(r,default=str))
    return 0 if r["status"]=="PASS" else 1

if __name__=="__main__":raise SystemExit(main())
