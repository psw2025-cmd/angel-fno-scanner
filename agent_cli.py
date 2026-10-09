#!/usr/bin/env python3
"""
Unified Agent CLI & Python SDK for Angel One F&O Prediction & Intelligence Engine.

Provides external AI agents, automated connectors, CI/CD runners, and humans with
read-only query and verification capabilities for automation and humans.
Production writes are fail-closed behind the market_bot writer guard.
"""

import argparse
import datetime
import json
import os
import re
import sys

from credentials import require_authoritative_sheet_id

# Ensure repository root is on sys.path
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
if REPO_DIR not in sys.path:
    sys.path.insert(0, REPO_DIR)

from angel_prediction_engine import (
    get_bigquery_client,
    get_gspread_client,
    get_angel_client,
    run_prediction_pipeline,
    generate_next_day_gap_picks,
    reconcile_next_day_gap_trades,
    NEXT_DAY_GAP_PATH,
    GAP_RECON_HISTORY_PATH,
    BQ_PROJECT_ID,
    BQ_DATASET_ID,
    SHEET_ID,
    STATE_PATH,
    CALIBRATION_STATE_PATH
)
from verify_all_sheets_and_engine import (
    audit_sheets,
    audit_bigquery,
    audit_engine_state,
    audit_publication
)


def validate_query_inputs(symbol=None, limit=10):
    if symbol is not None:
        if not isinstance(symbol, str):
            raise ValueError("Invalid symbol")
        symbol = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9&_-]{1,32}", symbol):
            raise ValueError("Invalid symbol")
    if isinstance(limit, bool) or not str(limit).isdigit() or not 1 <= int(limit) <= 1000:
        raise ValueError("Limit must be an integer from 1 to 1000")
    return symbol, int(limit)


def get_bq():
    return get_bigquery_client()


def query_predictions(symbol=None, limit=10):
    symbol, limit = validate_query_inputs(symbol, limit)
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
    _, limit = validate_query_inputs(limit=limit)
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
    _, limit = validate_query_inputs(limit=limit)
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
    symbol, limit = validate_query_inputs(symbol, limit)
    client = get_bq()
    conditions = [
        "NOT (title = 'Markets maintain bullish momentum ahead of pre-close' "
        "AND source = 'Moneycontrol' AND news_type = 'MARKET_PULSE' "
        "AND canonical_url = 'https://www.moneycontrol.com')"
    ]
    if symbol:
        conditions.append(f"UPPER(symbol) = '{symbol.strip().upper()}'")
    where_clause = "WHERE " + " AND ".join(conditions)
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
    publication_ok, publication_summary = audit_publication()
    state_summary = "Prediction state and calibration state verified" if state_ok else "Engine state files missing"

    all_passed = sheets_ok and bq_ok and state_ok and publication_ok
    return {
        "status": "PASS" if all_passed else "FAIL",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sheets_audit": {"passed": sheets_ok, "summary": sheets_summary},
        "bigquery_audit": {"passed": bq_ok, "summary": bq_summary},
        "publication": {"passed": publication_ok, "summary": publication_summary},
        "engine_state": {"passed": state_ok, "summary": state_summary}
    }


def query_next_day_gap(limit=5):
    """Retrieves Top 5 CE and PE candidates for next-day gap opening with complete micro-details."""
    if os.path.exists(NEXT_DAY_GAP_PATH):
        try:
            with open(NEXT_DAY_GAP_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "timestamp_ist": data.get("timestamp_ist", ""),
                    "top_ce_picks": data.get("top_ce_picks", [])[:limit],
                    "top_pe_picks": data.get("top_pe_picks", [])[:limit]
                }
        except Exception:
            pass
    # Fallback to generating from latest predictions
    preds = query_predictions(limit=250)
    picks = generate_next_day_gap_picks(preds)
    return {
        "timestamp_ist": picks.get("timestamp_ist", ""),
        "top_ce_picks": picks.get("top_ce_picks", [])[:limit],
        "top_pe_picks": picks.get("top_pe_picks", [])[:limit]
    }


def export_snapshots(output_dir="data"):
    """Fail closed on metadata; stage all exports and restore old bundle on errors."""
    import subprocess
    import shutil
    from pathlib import Path
    from tools.atomic_snapshots import publish_bundle
    meta_path = os.environ.get("ANGEL_CYCLE_METADATA_FILE")
    if not meta_path:
        raise RuntimeError("ANGEL_CYCLE_METADATA_FILE missing; snapshot export blocked")
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    fields = ("source_timestamp", "run_id", "git_sha", "cycle_id", "market_session")
    if any(not meta.get(k) for k in fields):
        raise RuntimeError("cycle metadata incomplete; snapshot export blocked")
    if meta.get("data_freshness_status") != "EXCHANGE_VERIFIED":
        raise RuntimeError("cycle metadata not exchange verified; snapshot export blocked")
    subprocess.check_call([sys.executable, str(Path(REPO_DIR) / "tools" / "check_freshness.py"),
        "--source-timestamp", str(meta["source_timestamp"]), "--run-id", str(meta["run_id"]),
        "--git-sha", str(meta["git_sha"]), "--cycle-id", str(meta["cycle_id"]),
        "--market-session", str(meta["market_session"]), "--expected-metadata", meta_path])
    safe_run_id = re.sub(r"[^A-Za-z0-9_-]", "_", str(meta["run_id"]))
    stage = Path(REPO_DIR) / "scratch" / "staging" / safe_run_id
    if stage.exists():
        raise RuntimeError("staging directory already exists; refusing concurrent export")
    stage.mkdir(parents=True)
    try:
        rel_stage = str(stage.relative_to(REPO_DIR))
        result = _export_snapshots_unstaged(output_dir=rel_stage, verified_source_timestamp=str(meta["source_timestamp"]))
        names = ("latest_predictions.json", "top_gapup.json", "breakouts.json",
                 "market_news.json", "system_health.json", "next_day_gap_predictions.json", "summary.md")
        publish_bundle(stage, Path(REPO_DIR) / output_dir, names)
        result["directory"] = str(Path(REPO_DIR) / output_dir)
        return result
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _export_snapshots_unstaged(output_dir="data", verified_source_timestamp=None):
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

    # 6. Next-Day Pre-Close Gap Picks snapshot
    next_day_picks = query_next_day_gap(limit=10)
    with open(os.path.join(target_dir, "next_day_gap_predictions.json"), "w", encoding="utf-8") as f:
        json.dump(next_day_picks, f, indent=2)

    # 7. Pre-rendered Markdown Summary for GitHub / LLMs
    # Derive timestamp strictly from validated predictions rather than wall clock
    feed_candidates = [
        p.get("exchFeedTime") or p.get("timestamp")
        for p in (preds or [])
        if p.get("exchFeedTime") or p.get("timestamp")
    ]
    if not feed_candidates:
        all_recs = (next_day_picks.get("top_ce_picks") or []) + (next_day_picks.get("top_pe_picks") or [])
        feed_candidates = [
            p.get("exchFeedTime") or p.get("timestamp")
            for p in all_recs
            if p.get("exchFeedTime") or p.get("timestamp")
        ]
    if not feed_candidates and verified_source_timestamp:
        # Cycle metadata is validated by check_freshness before export; never use writer clock.
        feed_candidates = [verified_source_timestamp]
    if not feed_candidates:
        raise ValueError("Missing exchange timestamp and verified cycle provenance; fail-closed")
    now_str = str(min(feed_candidates))
    md = f"""# Angel One F&O Prediction & Market Intelligence Snapshot
**Generated**: `{now_str}` | **System Status**: `🟢 {health['status']}`

## 🌆 3:00 - 3:40 PM Pre-Close: Next-Day Gap-Up (CE) Picks
| Rank | Symbol | Target Strike | Contract | Entry LTP | Stop Loss (-15%) | Target (+50%) | Expected Gap % | Conviction % | Institutional Rationale |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for idx, c in enumerate(next_day_picks.get("top_ce_picks", [])[:5], start=1):
        md += f"| {idx} | **{c.get('symbol', '')}** | `{c.get('target_strike', '')}` | `{c.get('contract_symbol', '')}` | ₹{float(c.get('entry_ltp', 0)):.2f} | ₹{float(c.get('stop_loss_ltp', 0)):.2f} | ₹{float(c.get('target_ltp', 0)):.2f} | **{float(c.get('expected_gap_pct', 0)):+.2f}%** | {float(c.get('conviction_pct', 0)):.1f}% | {c.get('why_rationale', '')[:80]} |\n"

    md += """
## 🌆 3:00 - 3:40 PM Pre-Close: Next-Day Gap-Down (PE) Picks
| Rank | Symbol | Target Strike | Contract | Entry LTP | Stop Loss (-15%) | Target (+60%) | Expected Gap % | Conviction % | Institutional Rationale |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""
    for idx, c in enumerate(next_day_picks.get("top_pe_picks", [])[:5], start=1):
        md += f"| {idx} | **{c.get('symbol', '')}** | `{c.get('target_strike', '')}` | `{c.get('contract_symbol', '')}` | ₹{float(c.get('entry_ltp', 0)):.2f} | ₹{float(c.get('stop_loss_ltp', 0)):.2f} | ₹{float(c.get('target_ltp', 0)):.2f} | **{float(c.get('expected_gap_pct', 0)):+.2f}%** | {float(c.get('conviction_pct', 0)):.1f}% | {c.get('why_rationale', '')[:80]} |\n"

    md += """
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

    print(f"[OK] Snapshots exported successfully: latest_predictions.json, top_gapup.json, breakouts.json, market_news.json, system_health.json, next_day_gap_predictions.json, summary.md")
    return {"status": "SUCCESS", "directory": target_dir, "exported_files": 7}


def format_output(data, output_format="json", title=None):
    if output_format == "json":
        print(json.dumps(data, indent=2))
        return

    # Specialized rendering for Next-Day Gap Picks
    if isinstance(data, dict) and ("top_ce_picks" in data or "top_pe_picks" in data):
        if title:
            print(f"## {title}\n")
        print(f"**Snapshot IST**: `{data.get('timestamp_ist', '')}`\n")

        print("### 🌅 Top Next-Day Gap-Up Call (CE) Picks")
        print("| Rank | Symbol | Target Strike | Contract | Entry LTP | Stop Loss (-15%) | Target (+50%) | Expected Gap % | Conviction % | Institutional Rationale |")
        print("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        for idx, c in enumerate(data.get("top_ce_picks", []), start=1):
            print(f"| {idx} | **{c.get('symbol', '')}** | `{c.get('target_strike', '')}` | `{c.get('contract_symbol', '')}` | ₹{float(c.get('entry_ltp', 0)):.2f} | ₹{float(c.get('stop_loss_ltp', 0)):.2f} | ₹{float(c.get('target_ltp', 0)):.2f} | **{float(c.get('expected_gap_pct', 0)):+.2f}%** | {float(c.get('conviction_pct', 0)):.1f}% | {c.get('why_rationale', '')[:80]} |")

        print("\n### 💥 Top Next-Day Gap-Down Put (PE) Picks")
        print("| Rank | Symbol | Target Strike | Contract | Entry LTP | Stop Loss (-15%) | Target (+60%) | Expected Gap % | Conviction % | Institutional Rationale |")
        print("| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        for idx, c in enumerate(data.get("top_pe_picks", []), start=1):
            print(f"| {idx} | **{c.get('symbol', '')}** | `{c.get('target_strike', '')}` | `{c.get('contract_symbol', '')}` | ₹{float(c.get('entry_ltp', 0)):.2f} | ₹{float(c.get('stop_loss_ltp', 0)):.2f} | ₹{float(c.get('target_ltp', 0)):.2f} | **{float(c.get('expected_gap_pct', 0)):+.2f}%** | {float(c.get('conviction_pct', 0)):.1f}% | {c.get('why_rationale', '')[:80]} |")
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
    parser.add_argument("--next-day-gap", action="store_true", help="Get Top 5 Next-Day Pre-Close (15:00-15:40 IST) Gap-Up (CE) and Gap-Down (PE) candidates with micro-details")
    parser.add_argument("--query-news", nargs="?", const="ALL", help="Get multi-source news for a symbol or ALL")
    parser.add_argument("--run-cycle", action="store_true", help="Writer-gated production pipeline pass (market_bot only)")
    parser.add_argument("--force-pre-close", action="store_true", help="Writer-gated pre-close journaling (market_bot only)")
    parser.add_argument("--reconcile-gap", action="store_true", help="Writer-gated overnight reconciliation (market_bot only)")
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
    elif args.next_day_gap:
        res = query_next_day_gap(limit=args.limit)
        format_output(res, args.format, title="Top Next-Day Pre-Close (3:00-3:40 PM) Gap Candidates")
    elif args.query_news:
        sym = None if args.query_news == "ALL" else args.query_news
        res = query_news(symbol=sym, limit=args.limit)
        format_output(res, args.format, title=f"Multi-Source Market News for {sym or 'Latest Feed'}")
    elif args.run_cycle:
        print("[INFO] Triggering live prediction pipeline pass via Agent CLI...")
        run_prediction_pipeline(bypass_market_check=True)
        export_snapshots()
        print("[SUCCESS] Prediction pipeline pass complete!")
    elif args.force_pre_close:
        print("[INFO] Forcing 3:00-3:40 PM Pre-Close Journaling Pass...")
        run_prediction_pipeline(bypass_market_check=True, force_pre_close=True)
        export_snapshots()
        print("[SUCCESS] Pre-close journaling pass complete!")
    elif args.reconcile_gap:
        print("[INFO] Executing overnight gap paper trade reconciliation...")
        gc = get_gspread_client()
        sh = gc.open_by_key(require_authoritative_sheet_id(SHEET_ID))
        bq_client = get_bigquery_client()
        smartApi = get_angel_client()
        preds = query_predictions(limit=250)
        now_dt = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        reconcile_next_day_gap_trades(smartApi, sh, bq_client, preds, now_str, now_dt)
        print("[SUCCESS] Overnight gap trade reconciliation complete!")
    elif args.verify:
    elif args.verify:
        if getattr(args, 'json_only', False):
            import io, contextlib
            _buf = io.StringIO()
            with contextlib.redirect_stdout(_buf):
                res = run_full_verification()
            format_output(res, "json", title="")
        else:
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
