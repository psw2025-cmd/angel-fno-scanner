#!/usr/bin/env python3
"""
Unified Agent CLI & Python SDK for Angel One F&O Prediction & Intelligence Engine.

Provides external AI agents, automated connectors, CI/CD runners, and humans with
full programmatic read, write, execution, verification, and inspection capabilities
directly through GitHub and terminal environments.
"""

import argparse
import datetime
import json
import os
import sys

# Ensure repository root is on sys.path
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

from angel_prediction_engine import (
    get_bigquery_client,
    get_gspread_client,
    run_prediction_pipeline,
    BQ_PROJECT_ID,
    BQ_DATASET_ID,
    SHEET_ID,
    STATE_PATH,
    CALIBRATION_STATE_PATH
)
from verify_all_sheets_and_engine import (
    audit_sheets,
    audit_bigquery,
    audit_engine_state
)


def get_bq():
    return get_bigquery_client()


def query_predictions(symbol=None, limit=10):
    client = get_bq()
    if symbol:
        sql = f"""
        SELECT *
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.option_predictions_live`
        WHERE UPPER(symbol) = '{symbol.strip().upper()}'
        LIMIT 1
        """
    else:
        sql = f"""
        SELECT *
        FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.option_predictions_live`
        ORDER BY rank ASC
        LIMIT {limit}
        """
    rows = [dict(r) for r in client.query(sql).result()]
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                r[k] = v.isoformat()
    return rows


def query_top_gapup(limit=10):
    client = get_bq()
    sql = f"""
    SELECT rank, symbol, gap_direction, expected_gap_pct, pre_open_conviction_pct, target_open_strike,
           spot_ltp, atm_strike, ce_ltp, ce_chg_pct, pe_ltp, pe_chg_pct,
           ce_oi, ce_oi_change_pct, ce_iv, ce_delta, ce_gamma,
           action_rating, directional_bias, intensity_score, confidence_pct,
           news_severity_level, news_source_tier, market_confirmation, expected_move_band,
           news_sentiment_score, top_news_headline
    FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.option_predictions_live`
    WHERE expected_gap_pct > 0
    ORDER BY expected_gap_pct DESC
    LIMIT {limit}
    """
    rows = [dict(r) for r in client.query(sql).result()]
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                r[k] = v.isoformat()
    return rows


def query_top_breakouts(limit=5):
    client = get_bq()
    sql_ce = f"""
    SELECT rank, symbol, action_rating, directional_bias, ce_win_prob, intensity_score,
           spot_ltp, atm_strike, ce_ltp, ce_chg_pct, ce_iv, target_open_strike, expected_gap_pct, top_news_headline
    FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.option_predictions_live`
    WHERE directional_bias LIKE '%CALL%' AND action_rating NOT LIKE '%AVOID%'
    ORDER BY rank ASC
    LIMIT {limit}
    """
    sql_pe = f"""
    SELECT rank, symbol, action_rating, directional_bias, pe_win_prob, intensity_score,
           spot_ltp, atm_strike, pe_ltp, pe_chg_pct, pe_iv, target_open_strike, expected_gap_pct, top_news_headline
    FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.option_predictions_live`
    WHERE directional_bias LIKE '%PUT%' AND action_rating NOT LIKE '%AVOID%'
    ORDER BY rank ASC
    LIMIT {limit}
    """
    ce_rows = [dict(r) for r in client.query(sql_ce).result()]
    pe_rows = [dict(r) for r in client.query(sql_pe).result()]
    return {"top_ce_breakouts": ce_rows, "top_pe_breakdowns": pe_rows}


def query_news(symbol=None, limit=20):
    client = get_bq()
    where_clause = f"WHERE UPPER(symbol) = '{symbol.strip().upper()}'" if symbol else ""
    sql = f"""
    SELECT timestamp, symbol, title, news_type, sentiment, tone_score, impact_rating,
           severity_level, source_tier, positive_prob, negative_prob, already_priced_in_prob,
           market_confirmation, expected_move_band, source, source_url
    FROM `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.market_news_sentiment`
    {where_clause}
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    rows = [dict(r) for r in client.query(sql).result()]
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (datetime.datetime, datetime.date)):
                r[k] = v.isoformat()
    return rows


def run_full_verification():
    sheets_ok, sheets_summary = audit_sheets()
    bq_ok, bq_summary = audit_bigquery()
    state_ok = audit_engine_state()
    state_summary = "Prediction state and calibration state verified" if state_ok else "Engine state files missing"

    all_passed = sheets_ok and bq_ok and state_ok
    return {
        "status": "PASS" if all_passed else "FAIL",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sheets_audit": {"passed": sheets_ok, "summary": sheets_summary},
        "bigquery_audit": {"passed": bq_ok, "summary": bq_summary},
        "engine_state": {"passed": state_ok, "summary": state_summary}
    }


def export_snapshots(output_dir="data"):
    target_dir = os.path.join(REPO_DIR, output_dir)
    os.makedirs(target_dir, exist_ok=True)

    print(f"[INFO] Exporting pre-rendered data snapshots to {target_dir}...")
    
    # 1. Full predictions snapshot
    preds = query_predictions(limit=250)
    with open(os.path.join(target_dir, "latest_predictions.json"), "w", encoding="utf-8") as f:
        json.dump(preds, f, indent=2)

    # 2. Top Gap Up snapshot
    gapup = query_top_gapup(limit=20)
    with open(os.path.join(target_dir, "top_gapup.json"), "w", encoding="utf-8") as f:
        json.dump(gapup, f, indent=2)

    # 3. Breakouts snapshot
    breakouts = query_top_breakouts(limit=10)
    with open(os.path.join(target_dir, "breakouts.json"), "w", encoding="utf-8") as f:
        json.dump(breakouts, f, indent=2)

    # 4. News sentiment snapshot
    news = query_news(limit=50)
    with open(os.path.join(target_dir, "market_news.json"), "w", encoding="utf-8") as f:
        json.dump(news, f, indent=2)

    # 5. System Health snapshot
    health = run_full_verification()
    with open(os.path.join(target_dir, "system_health.json"), "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2)

    # 6. Pre-rendered Markdown Summary for GitHub / LLMs
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    md = f"""# Angel One F&O Prediction & Market Intelligence Snapshot
**Generated**: `{now_str}` | **System Status**: `🟢 {health['status']}`

## 🌅 Top 5 Pre-Market 9:15 AM Gap-Up Picks
| Rank | Symbol | Target Strike | Expected Gap % | Conviction % | CE LTP | Live Velocity | Top Catalyst Headline |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for r in gapup[:5]:
        exp_gap = float(r.get('expected_gap_pct') or 0.0)
        conv = float(r.get('pre_open_conviction_pct') or 0.0)
        ce_ltp = float(r.get('ce_ltp') or 0.0)
        ce_chg = float(r.get('ce_chg_pct') or 0.0)
        headline = (r.get('top_news_headline') or "Market momentum and order book buildup")[:60]
        md += f"| {r.get('rank', 1)} | **{r.get('symbol', '')}** | `{r.get('target_open_strike', '')}` | **+{exp_gap:.2f}%** | {conv:.1f}% | ₹{ce_ltp:.2f} | +{ce_chg:.1f}% | {headline} |\n"

    md += """
## 🏆 Top Conviction Call (CE) Breakouts
| Rank | Symbol | Action Rating | Win Prob % | Spot LTP | CE LTP | Target Strike |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
"""
    for r in breakouts.get("top_ce_breakouts", [])[:5]:
        spot = float(r.get('spot_ltp') or 0.0)
        ce_ltp = float(r.get('ce_ltp') or 0.0)
        prob = float(r.get('ce_win_prob') or 0.0)
        md += f"| {r.get('rank', 1)} | **{r.get('symbol', '')}** | {r.get('action_rating', '')} | {prob:.1f}% | ₹{spot:.2f} | ₹{ce_ltp:.2f} | `{r.get('target_open_strike', '')}` |\n"

    md += """
## 💥 Top Conviction Put (PE) Breakdowns
| Rank | Symbol | Action Rating | Win Prob % | Spot LTP | PE LTP | Target Strike |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: |
"""
    for r in breakouts.get("top_pe_breakdowns", [])[:5]:
        spot = float(r.get('spot_ltp') or 0.0)
        pe_ltp = float(r.get('pe_ltp') or 0.0)
        prob = float(r.get('pe_win_prob') or 0.0)
        md += f"| {r.get('rank', 1)} | **{r.get('symbol', '')}** | {r.get('action_rating', '')} | {prob:.1f}% | ₹{spot:.2f} | ₹{pe_ltp:.2f} | `{r.get('target_open_strike', '')}` |\n"

    with open(os.path.join(target_dir, "summary.md"), "w", encoding="utf-8") as f:
        f.write(md)

    print(f"[OK] Snapshots exported successfully: latest_predictions.json, top_gapup.json, breakouts.json, market_news.json, system_health.json, summary.md")
    return {"status": "SUCCESS", "directory": target_dir, "exported_files": 6}


def format_output(data, output_format="json", title=None):
    if output_format == "json":
        print(json.dumps(data, indent=2))
        return

    # Markdown format rendering
    if title:
        print(f"### {title}\n")

    if isinstance(data, list) and data:
        keys = list(data[0].keys())
        print("| " + " | ".join(keys) + " |")
        print("| " + " | ".join(["---"] * len(keys)) + " |")
        for row in data:
            print("| " + " | ".join(str(row.get(k, "")) for k in keys) + " |")
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                print(f"\n#### {k.upper()}\n")
                keys = list(v[0].keys())
                print("| " + " | ".join(keys) + " |")
                print("| " + " | ".join(["---"] * len(keys)) + " |")
                for row in v:
                    print("| " + " | ".join(str(row.get(x, "")) for x in keys) + " |")
            else:
                print(f"- **{k}**: {v}")


def main():
    parser = argparse.ArgumentParser(description="Unified Agent CLI & Python SDK for Angel One F&O Prediction Engine")
    parser.add_argument("--predict", nargs="?", const="ALL", help="Get prediction for a symbol (e.g. --predict MAHABANK) or ALL")
    parser.add_argument("--top-gapup", action="store_true", help="Get Top Gap-Up CE explosion picks with proof")
    parser.add_argument("--top-breakouts", action="store_true", help="Get Top CE breakout and PE breakdown candidates")
    parser.add_argument("--query-news", nargs="?", const="ALL", help="Get multi-source news for a symbol or ALL")
    parser.add_argument("--run-cycle", action="store_true", help="Trigger a live prediction pipeline pass (bypasses sleep)")
    parser.add_argument("--verify", action="store_true", help="Run 17-tab forensic audit across Google Sheets, BigQuery and Engine")
    parser.add_argument("--export-snapshots", action="store_true", help="Export pre-rendered data snapshots to data/ directory")
    parser.add_argument("--limit", type=int, default=10, help="Result limit (default: 10)")
    parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (json or markdown)")

    args = parser.parse_args()

    if args.predict:
        sym = None if args.predict == "ALL" else args.predict
        res = query_predictions(symbol=sym, limit=args.limit)
        format_output(res, args.format, title=f"Option Predictions for {sym or 'Top ' + str(args.limit)}")
    elif args.top_gapup:
        res = query_top_gapup(limit=args.limit)
        format_output(res, args.format, title="Top Gap-Up (CE Explosion) Predictions")
    elif args.top_breakouts:
        res = query_top_breakouts(limit=args.limit)
        format_output(res, args.format, title="Top Conviction CE Breakouts & PE Breakdowns")
    elif args.query_news:
        sym = None if args.query_news == "ALL" else args.query_news
        res = query_news(symbol=sym, limit=args.limit)
        format_output(res, args.format, title=f"Multi-Source Market News for {sym or 'Latest Feed'}")
    elif args.run_cycle:
        print("[INFO] Triggering live prediction pipeline pass via Agent CLI...")
        run_prediction_pipeline(bypass_market_check=True)
        export_snapshots()
        print("[SUCCESS] Prediction pipeline pass complete!")
    elif args.verify:
        res = run_full_verification()
        format_output(res, args.format, title="Forensic System Verification Audit")
        if res["status"] != "PASS":
            sys.exit(1)
    elif args.export_snapshots:
        res = export_snapshots()
        format_output(res, args.format, title="Snapshot Export Status")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
