#!/usr/bin/env python3
"""Local paper-only runner. Fail closed until real Angel option-contract manifest is supplied."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
IST = ZoneInfo("Asia/Kolkata")
TABLE = "fno-angel-prod-1790444589.PAPER_TRADING_SANDBOX_PHASE2.prediction_ledger"

def load_env(path):
    if not path.is_file():
        raise RuntimeError("Missing local .env; see .env.phase2.example")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip().isidentifier():
            raise ValueError("Malformed .env line")
        os.environ[key.strip()] = value.strip().strip('"').strip("'")

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip()

def serialize_raw_snapshot(snapshot):
    """Return one valid JSON document with a real LF; hash the written bytes."""
    return json.dumps(snapshot, sort_keys=True, indent=2, allow_nan=False) + "\n"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase2/angel_contracts.local.json")
    parser.add_argument("--push", action="store_true", help="Explicitly push verified receipt to test-framework")
    args = parser.parse_args()
    from nse_calendar import trading_status
    if trading_status()["market_closed"]:
        print("MARKET_CLOSED: Phase 2 skipped without quote or ledger mutation")
        return
    if (ROOT / ".env").is_file():
        load_env(ROOT / ".env")
    os.environ["PAPER_MODE"] = "1"
    os.environ["LIVE_ORDER_AUTHORITY"] = "0"
    os.environ["PHASE2_PAPER_LEDGER_TABLE"] = TABLE
    os.environ["PHASE2_SOURCE_KIND"] = "ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT"
    from phase2.angel_instruments import discover
    from phase2.option_stream import enforce_paper_mode
    from phase2.angel_readonly import AngelReadOnlyProvider
    from phase2.model import FeatureEngine
    from phase2.heuristic import V1HeuristicModel
    from phase2.daily_close import execute, canonical_hash
    from phase2.local_publisher import LocalArtifactPublisher
    from phase2.option_dna import snapshot_dna, structure_watch
    enforce_paper_mode()
    target_branch = os.getenv("PAPER_LEDGER_BRANCH", "test-framework")
    if target_branch not in ("main", "test-framework") or git("branch", "--show-current") != target_branch:
        raise RuntimeError("Unexpected paper ledger branch")
    manifest_path = ROOT / args.manifest
    manifest, master_sha256 = discover(manifest_path)
    print("ANGEL_INSTRUMENT_MASTER_SHA256", master_sha256)
    broker = AngelReadOnlyProvider()
    raw = []
    for item in manifest:
        quote = broker.quote("NFO", item["tradingsymbol"], item["symboltoken"])
        if quote.get("tradingSymbol") != item["tradingsymbol"]:
            raise RuntimeError("Quote trading symbol mismatch")
        raw.append({"contract": item, "quote": quote})
    snapshot = {"source_kind": os.environ["PHASE2_SOURCE_KIND"], "captured_at": datetime.now(IST).isoformat(), "instrument_master_sha256": master_sha256, "quotes": raw}
    raw_path = ROOT / "data" / "raw_snapshot.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(serialize_raw_snapshot(snapshot), encoding="utf-8")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    print("REAL_BROKER_RAW_SNAPSHOT_SHA256", digest)
    def num(value, field):
        try:
            v = float(value)
            if not __import__("math").isfinite(v) or v < 0:
                raise ValueError("Invalid numeric quote")
            return v
        except (TypeError, ValueError):
            raise ValueError("Required broker quote field missing or invalid: " + field)
    dna_rows = []
    rows = []
    totals = {}
    entries = {}
    for entry in raw:
        item, q = entry["contract"], entry["quote"]
        depth = q.get("depth") or {}
        buy, sell = depth.get("buy") or [], depth.get("sell") or []
        if not buy or not sell:
            raise RuntimeError("Missing executable bid/ask depth")
        bid, ask = num(buy[0].get("price"), "bid_price"), num(sell[0].get("price"), "ask_price")
        if bid <= 0 or ask < bid:
            raise RuntimeError("Invalid executable spread")
        oi = num(q.get("openInterest") if q.get("openInterest") is not None else q.get("opnInterest"), "openInterest/opnInterest")
        volume = num(q.get("tradeVolume"), "tradeVolume")
        key = (item["underlying"], item["expiry"])
        totals.setdefault(key, {"CE": 0, "PE": 0})[item["option_type"]] += oi
        dna = snapshot_dna(q)
        dna_rows.append({"tradingsymbol":item["tradingsymbol"],"symboltoken":str(item["symboltoken"]),"underlying":item["underlying"],"expiry":item["expiry"],"option_type":item["option_type"],"oi":oi,"volume":volume,**dna})
        rows.append({**item, "oi": oi, "volume": volume, "spread_pct": dna["spread_pct"], "iv_rank": None})
        identity = (item["underlying"], item["expiry"], item["strike"], item["option_type"])
        if identity in entries:
            raise RuntimeError("Duplicate entry contract identity")
        entries[identity] = {"underlying": item["underlying"], "exchange": "NFO", "expiry": item["expiry"], "strike": item["strike"], "option_type": item["option_type"], "tradingsymbol": item["tradingsymbol"], "symboltoken": str(item["symboltoken"]), "captured_at": snapshot["captured_at"], "entry_bid": bid, "entry_ask": ask, "entry_price": ask, "entry_price_method": "SNAPSHOT_BEST_ASK_NOT_FILLED"}
    contracts = []
    for row in rows:
        counts = totals[(row["underlying"], row["expiry"])]
        if counts["CE"] <= 0 or counts["PE"] <= 0:
            raise RuntimeError("Observed PCR unavailable")
        contracts.append({"symbol": row["underlying"], "expiry": row["expiry"], "strike": row["strike"], "option_type": row["option_type"], "oi": row["oi"], "volume": row["volume"], "spread_pct": row["spread_pct"], "pcr": counts["PE"]/counts["CE"], "iv_rank": None})
    features = FeatureEngine().transform({"contracts": contracts})
    ranking = V1HeuristicModel().predict(features)
    if not ranking:
        raise RuntimeError("No ranked contracts")
    ranked_entries = []
    for ranked in ranking:
        identity = (ranked["symbol"], ranked["expiry"], ranked["strike"], ranked["option_type"])
        if identity not in entries:
            raise RuntimeError("Ranked contract has no authenticated quote entry")
        e = {**entries[identity], "rank": ranked["rank"]}
        ranked_entries.append(e)
        ranked["exchange"] = e["exchange"]
        ranked["tradingsymbol"] = e["tradingsymbol"]
        ranked["symboltoken"] = e["symboltoken"]
        ranked["entry_bid"] = e["entry_bid"]
        ranked["entry_ask"] = e["entry_ask"]
        ranked["entry_price"] = e["entry_price"]
        ranked["entry_captured_at"] = e["captured_at"]
        ranked["entry_price_method"] = e["entry_price_method"]
    stamp = snapshot["captured_at"]
    structure = structure_watch(ranking)
    prediction = {"run_id": canonical_hash({"raw_snapshot_sha256": digest, "model_version": V1HeuristicModel.version}), "created_at": stamp, "mode": "PAPER", "live_order_authority": 0, "source_timestamp": stamp, "source_hash": digest, "features_hash": canonical_hash(features), "model_version": V1HeuristicModel.version, "ranking": ranking, "provenance": {"source_kind": os.environ["PHASE2_SOURCE_KIND"], "instrument_master_sha256": master_sha256, "snapshot_kind": "BROKER_QUOTE_CAPTURE_NOT_OFFICIAL_CLOSE", "pcr_scope": "SELECTED_NEAREST_EXPIRY_STRIKES_ONLY"}}
    prediction["prediction_hash"] = canonical_hash(prediction)
    receipt_path = ROOT / "data" / "paper_ledger" / "receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = LocalArtifactPublisher(receipt_path).publish_once(prediction)
    assert receipt["prediction_hash"] == canonical_hash({k:v for k,v in prediction.items() if k != "prediction_hash"})
    print("PAPER_PREDICTION_SHA256", receipt["prediction_hash"])
    entry_manifest = {"prediction_hash": receipt["prediction_hash"], "source_hash": digest, "paper_mode": 1, "live_order_authority": 0, "contracts": ranked_entries}
    entry_path = ROOT / "data" / "paper_ledger" / ("entry_" + receipt["prediction_hash"] + ".json")
    if entry_path.exists() and json.loads(entry_path.read_text(encoding="utf-8")) != entry_manifest:
        raise RuntimeError("Immutable entry manifest conflict")
    entry_path.write_text(json.dumps(entry_manifest, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    anomaly = {"schema_version":"OPTION_DNA_V1","paper_mode":1,"live_order_authority":0,"prediction_hash":receipt["prediction_hash"],"source_hash":digest,"captured_at":stamp,"contracts":dna_rows,"structure_watch":structure,"limitations":["IV_AND_THETA_UNAVAILABLE_NO_VERIFIED_INPUT","TOP_BOTTOM_ARE_OI_ONLY_HYPOTHESES_NOT_CONFIRMED","VOLUME_OI_RATIO_IS_NOT_OI_DELTA"]}
    anomaly_path = ROOT/"data"/"anomaly_logs"/("dna_"+receipt["prediction_hash"]+".json")
    anomaly_path.parent.mkdir(parents=True,exist_ok=True)
    if anomaly_path.exists() and json.loads(anomaly_path.read_text(encoding="utf-8")) != anomaly: raise RuntimeError("Immutable DNA ledger conflict")
    anomaly_path.write_text(json.dumps(anomaly,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    if args.push:
        if git("status", "--porcelain", "--", "data/paper_ledger/receipt.json"):
            git("add", "--", "data/paper_ledger/receipt.json", str(entry_path.relative_to(ROOT)), str(anomaly_path.relative_to(ROOT)))
            git("commit", "-m", "data: local read-only Angel snapshot paper receipt " + receipt["prediction_hash"])
        if git("status", "--porcelain", "--", str(entry_path.relative_to(ROOT))):
            git("add", "--", str(entry_path.relative_to(ROOT)))
            git("commit", "-m", "data: immutable Phase 2 entry manifest " + receipt["prediction_hash"])
        git("add", "--", str(anomaly_path.relative_to(ROOT)))
        if git("diff", "--cached", "--name-only"):
            git("commit", "-m", "data: immutable Option DNA evidence " + receipt["prediction_hash"])
        git("push", "origin", "HEAD:" + target_branch)
        print("PAPER_LEDGER_COMMIT", git("rev-parse", "HEAD"))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PHASE2_FAIL_CLOSED:", exc, file=sys.stderr)
        sys.exit(1)
