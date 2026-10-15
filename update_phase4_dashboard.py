#!/usr/bin/env python3
"""Render a factual, paper-only dashboard from the verified Phase 3 report."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def git(*args):
    return subprocess.run(["git",*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
def main():
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY") != "0":
        raise RuntimeError("Paper-only guard failed")
    report = json.loads((ROOT/"pnl_report.json").read_text(encoding="utf-8"))
    if report["paper_mode"] != 1 or report["live_order_authority"] != 0:
        raise RuntimeError("Unsafe report")
    if report["evaluation_mode"] not in ("NEXT_DAY","INTRADAY_TEST"):
        raise RuntimeError("Unknown evaluation mode")
    rows = report["contracts"]
    if not rows: raise RuntimeError("Empty report")
    total = sum(float(x["theoretical_long_pnl_per_unit"]) for x in rows)
    receipt = json.loads((ROOT/"data/paper_ledger/receipt.json").read_text(encoding="utf-8"))
    latest = receipt["prediction_hash"]
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
    dna_path = ROOT/"data"/"anomaly_logs"/("dna_"+report["source_prediction_hash"]+".json")
    dna = json.loads(dna_path.read_text(encoding="utf-8")) if dna_path.exists() else None
    comparison_path = ROOT/"data"/"anomaly_logs"/("comparison_"+report["report_sha256"]+".json")
    comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.exists() else None
    if dna and (dna["prediction_hash"]!=report["source_prediction_hash"] or dna["paper_mode"]!=1 or dna["live_order_authority"]!=0): raise RuntimeError("Dashboard DNA linkage mismatch")
    if comparison and (comparison["report_sha256"]!=report["report_sha256"] or comparison["paper_mode"]!=1 or comparison["live_order_authority"]!=0): raise RuntimeError("Dashboard comparison linkage mismatch")
    dna_flags = sum(len(x["flags"]) for x in dna["contracts"]) if dna else None
    comparisons = sum(len(x["flags"]) for x in comparison["contracts"]) if comparison else None
    watches = dna["structure_watch"] if dna else []
    watch_rows = "".join(f"| {x[\u0027underlying\u0027]} | {x[\u0027expiry\u0027]} | {x[\u0027state\u0027]} | {x[\u0027selected_pcr\u0027]} |\\n" for x in watches)
    content = ("# Angel FNO paper dashboard\n\n"
      "**Read-only, theoretical paper figures. No actual fills, fees, taxes or investment return.**\n\n"
      "| Latest Phase 2 date (IST) | Latest Phase 2 prediction SHA-256 |\n|---|---|\n"
      f"| {payload['source_timestamp']} | `{latest}` |\n\n"
      "| Phase 3 evaluation | Source prediction SHA-256 | Contracts | Sum of per-unit theoretical long PnL (INR)* | Evaluated (IST) |\n|---|---|---:|---:|---|\n"
      f"| {report['status']} | `{report['source_prediction_hash']}` | {len(rows)} | {total:.8f} | {report['evaluated_at']} |\n\n"
      "\\n## Option DNA and market structure watch\\n\\n"
      f"Phase 2 anomaly flags: {dna_flags if dna_flags is not None else 'UNAVAILABLE (legacy)'}; Phase 3 comparison flags: {comparisons if comparisons is not None else 'UNAVAILABLE'}. IV/Theta: **UNAVAILABLE — no verified Greeks/time series**.\\n\\n"
      "| Underlying | Expiry | OI-only hypothesis | Selected-strike PCR |\\n|---|---|---|---:|\\n"
      + (watch_rows or "| — | — | INSUFFICIENT DATA | — |\\n")
      + "\\n**Top/bottom labels are unconfirmed OI imbalance watches, not reversal predictions.**\\n\\n"
      "*Unweighted sum of individual per-unit marks across distinct contracts; **not** tradable portfolio PnL. "
      "Entry at original ask, mark at comparison bid. The report is an intraday engineering test when so labelled. "
      "GitHub scheduled workflows may run late or fail closed on missing/stale broker data.\n")
    (ROOT/"DASHBOARD.md").write_text(content,encoding="utf-8")
    git("add","--","DASHBOARD.md")
    if git("diff","--cached","--name-only"):
        git("commit","-m","docs: refresh factual paper dashboard "+report["report_sha256"])
    git("push","origin","HEAD:test-framework")
    if git("rev-parse","HEAD") != git("ls-remote","origin","refs/heads/test-framework").split()[0]:
        raise RuntimeError("Dashboard remote verification failed")
    print("PAPER_DASHBOARD_REMOTE_VERIFIED",git("rev-parse","HEAD"))
if __name__=="__main__": main()
