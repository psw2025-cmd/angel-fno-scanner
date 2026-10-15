#!/usr/bin/env python3
"""Phase 3: fail-closed, read-only, theoretical long-option paper mark-to-market."""
import argparse
import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")
def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def positive(value, field):
    try:
        n = float(value)
        if not math.isfinite(n) or n <= 0: raise ValueError()
        return n
    except (ValueError, TypeError):
        raise ValueError("Missing or invalid positive " + field)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--force-intraday-test", action="store_true", help="Explicit same-day engineering test, never next-day PnL")
    args = ap.parse_args()
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY") != "0":
        raise RuntimeError("Paper-only environment flags required")
    from nse_calendar import trading_status, previous_trading_day
    if trading_status()["market_closed"]:
        print("MARKET_CLOSED: Phase 3 skipped without quote, PnL or dashboard mutation")
        return
    from phase2.option_stream import enforce_paper_mode
    from phase2.angel_readonly import AngelReadOnlyProvider
    from phase2.option_dna import snapshot_dna
    enforce_paper_mode()
    if git("branch", "--show-current") != "test-framework":
        raise RuntimeError("Must run on test-framework")
    now = datetime.now(IST)
    # Read immutable receipt revisions from Git history, never assume current mutable receipt is yesterday's.
    history = git("log", "--format=%H", "--", "data/paper_ledger/receipt.json").splitlines()
    candidates = []
    for commit in history:
        receipt = json.loads(git("show", commit + ":data/paper_ledger/receipt.json"))
        payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
        stamp = datetime.fromisoformat(payload["source_timestamp"]).astimezone(IST)
        if stamp.date() > now.date() or (stamp.date() == now.date() and not args.force_intraday_test): continue
        if receipt.get("paper_mode") != 1 or receipt.get("live_order_authority") != 0 or payload.get("mode") != "PAPER" or payload.get("live_order_authority") != 0:
            raise RuntimeError("Unsafe historical receipt")
        expected = digest({k:v for k,v in payload.items() if k != "prediction_hash"})
        if not (expected == payload.get("prediction_hash") == receipt.get("prediction_hash") == receipt["bigquery_merge_parameters"]["hash"]):
            raise RuntimeError("Historical prediction hash mismatch")
        if payload["source_hash"] != receipt["source_hash"]: raise RuntimeError("Source hash mismatch")
        candidates.append((stamp, receipt, payload))
    if not candidates: raise RuntimeError("No prior IST-day Phase 2 receipt in Git history")
    stamp, receipt, payload = max(candidates, key=lambda x:x[0])
    if args.force_intraday_test:
        if stamp.date() != now.date(): raise RuntimeError("Intraday test requires a same-day original receipt")
    else:
        previous_weekday = previous_trading_day(now.date())
        if stamp.date() != previous_weekday:
            raise RuntimeError("Latest receipt is not from previous weekday; exchange holidays require explicit validation")
    key = receipt["prediction_hash"]
    manifest_path = "data/paper_ledger/entry_" + key + ".json"
    try:
        entry = json.loads(git("show", "HEAD:" + manifest_path))
    except subprocess.CalledProcessError:
        raise RuntimeError("ENTRY_PROVENANCE_MISSING: Phase 2 receipt has no historical exact-token and timestamped entry premium manifest; cannot calculate honest PnL")
    if entry.get("prediction_hash") != key or entry.get("source_hash") != receipt["source_hash"] or entry.get("paper_mode") != 1 or entry.get("live_order_authority") != 0:
        raise RuntimeError("Entry manifest linkage or safety mismatch")
    rows = entry.get("contracts")
    if not isinstance(rows,list) or not rows: raise RuntimeError("Empty entry manifest")
    ranking = payload["ranking"]
    if len(rows) != len(ranking): raise RuntimeError("Entry manifest and ranking coverage mismatch")
    dna_path = "data/anomaly_logs/dna_" + key + ".json"
    try:
        original_dna = json.loads(git("show","HEAD:"+dna_path))
    except subprocess.CalledProcessError:
        original_dna = None  # Legacy receipts predate Option DNA; do not invent historical metrics.
    if original_dna is not None and (original_dna.get("prediction_hash")!=key or original_dna.get("source_hash")!=receipt["source_hash"] or original_dna.get("paper_mode")!=1 or original_dna.get("live_order_authority")!=0):
        raise RuntimeError("Option DNA source provenance mismatch")
    prior_by_token = {x["symboltoken"]:x for x in original_dna["contracts"]} if original_dna else {}
    broker = AngelReadOnlyProvider()
    results = []
    dna_comparisons = []
    seen = set()
    for item in rows:
        rank = item.get("rank")
        if type(rank) is not int or rank < 1 or rank > len(ranking) or rank in seen: raise RuntimeError("Duplicate/invalid rank")
        seen.add(rank)
        ref = ranking[rank-1]
        for k in ("symboltoken", "tradingsymbol", "entry_bid", "entry_ask", "entry_price"):
            if ref.get(k) != item.get(k) and not (k == "entry_price" and ref.get(k) == item.get("entry_ask")):
                raise RuntimeError("Receipt-to-manifest provenance mismatch: "+k)
        for k in ("expiry","strike","option_type"):
            if item.get(k) != ref.get(k): raise RuntimeError("Entry contract identity mismatch: "+k)
        if item.get("underlying") != ref.get("symbol") or item.get("exchange") != "NFO": raise RuntimeError("Entry underlying/exchange mismatch")
        entry_at = datetime.fromisoformat(item["captured_at"]).astimezone(IST)
        if entry_at.date() != stamp.date(): raise RuntimeError("Entry date not original source date")
        entry_ask = positive(item.get("entry_ask"),"entry_ask")
        entry_bid = positive(item.get("entry_bid"),"entry_bid")
        if entry_ask < entry_bid: raise RuntimeError("Invalid entry spread")
        token, symbol = str(item["symboltoken"]), str(item["tradingsymbol"])
        if not token.isdigit() or not symbol: raise RuntimeError("Invalid contract token/symbol")
        quote = broker.quote("NFO", symbol, token)
        if quote.get("tradingSymbol") != symbol: raise RuntimeError("Live symbol mismatch")
        depth = quote.get("depth") or {}
        buy, sell = depth.get("buy") or [], depth.get("sell") or []
        if not buy or not sell: raise RuntimeError("Current quote missing bid/ask")
        bid = positive(buy[0].get("price"),"current bid")
        ask = positive(sell[0].get("price"),"current ask")
        if ask < bid: raise RuntimeError("Crossed current spread")
        current_dna = snapshot_dna(quote,prior=prior_by_token.get(token))
        dna_comparisons.append({"rank":rank,"tradingsymbol":symbol,"symboltoken":token,**current_dna})
        pnl = bid-entry_ask
        results.append({"rank":rank,"underlying":item["underlying"],"expiry":item["expiry"],"strike":item["strike"],"option_type":item["option_type"],"exchange":"NFO","tradingsymbol":symbol,"symboltoken":token,"entry_captured_at":item["captured_at"],"entry_bid":entry_bid,"entry_ask":entry_ask,"current_bid":bid,"current_ask":ask,"broker_exchange_timestamp":quote.get("exchFeedTime"),"theoretical_long_pnl_per_unit":round(pnl,8),"theoretical_long_pnl_pct":round(100*pnl/entry_ask,8)})
    report = {"status":("INTRADAY_ENGINEERING_TEST_NOT_NEXT_DAY_PNL" if args.force_intraday_test else "THEORETICAL_PAPER_MARK_TO_MARKET_NOT_FILLED"),"evaluation_mode":("INTRADAY_TEST" if args.force_intraday_test else "NEXT_DAY"),"paper_mode":1,"live_order_authority":0,"source_prediction_hash":key,"source_hash":receipt["source_hash"],"source_timestamp":payload["source_timestamp"],"evaluated_at":now.isoformat(),"entry_manifest_sha256":digest(entry),"method":"LONG_ENTRY_ASK_TO_CURRENT_BID_PER_UNIT_EXCLUDES_FEES_TAXES","contracts":results}
    report["option_dna_status"] = "AVAILABLE" if original_dna else "LEGACY_ENTRY_DNA_UNAVAILABLE"
    report["option_dna_flags_count"] = sum(len(x["flags"]) for x in dna_comparisons)
    report["report_sha256"] = digest(report)
    comparison = {"schema_version":"OPTION_DNA_PHASE3_V1","paper_mode":1,"live_order_authority":0,"prediction_hash":key,"report_sha256":report["report_sha256"],"evaluated_at":now.isoformat(),"entry_dna_status":report["option_dna_status"],"contracts":dna_comparisons,"limitations":["IV_THETA_NOT_CALCULABLE_WITHOUT_VERIFIED_GREEKS_AND_TIME_SERIES","STALE_BROKER_TIMESTAMPS_ARE_NOT_NEW_MARKET_MOVEMENT"]}
    comparison_path = ROOT/"data"/"anomaly_logs"/("comparison_"+report["report_sha256"]+".json")
    comparison_path.parent.mkdir(parents=True,exist_ok=True)
    if comparison_path.exists() and json.loads(comparison_path.read_text(encoding="utf-8")) != comparison: raise RuntimeError("Immutable Phase 3 DNA comparison conflict")
    comparison_path.write_text(json.dumps(comparison,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    target = ROOT/"data"/"pnl_ledger"/(key+"_"+now.date().isoformat()+("_INTRADAY_TEST" if args.force_intraday_test else "")+".json")
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if json.loads(target.read_text(encoding="utf-8")) != report: raise RuntimeError("Existing daily report immutable; refusing overwrite")
    else:
        target.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    (ROOT/"pnl_report.json").write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    if args.push:
        git("add","--",str(target.relative_to(ROOT)),str(comparison_path.relative_to(ROOT)))
        if git("diff","--cached","--name-only"):
            git("commit","-m","data: Phase 3 theoretical paper PnL "+report["report_sha256"])
        git("push","origin","HEAD:test-framework")
        if git("rev-parse","HEAD") != git("ls-remote","origin","refs/heads/test-framework").split()[0]: raise RuntimeError("Remote push not confirmed")
    print("PHASE3_PNL_REPORT_SHA256",report["report_sha256"])
if __name__=="__main__":
    try: main()
    except Exception as exc:
        import sys
        print("PHASE3_FAIL_CLOSED:",exc,file=sys.stderr)
        sys.exit(1)
