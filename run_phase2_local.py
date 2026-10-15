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

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="phase2/angel_contracts.local.json")
    parser.add_argument("--push", action="store_true", help="Explicitly push verified receipt to test-framework")
    args = parser.parse_args()
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
    enforce_paper_mode()
    if git("branch", "--show-current") != "test-framework":
        raise RuntimeError("Checkout test-framework before executing")
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
    raw_path.write_text(json.dumps(snapshot, sort_keys=True, indent=2, allow_nan=False) + "\\n", encoding="utf-8")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    print("REAL_BROKER_RAW_SNAPSHOT_SHA256", digest)
    def num(value):
        try:
            v = float(value)
            if not __import__("math").isfinite(v) or v < 0:
                raise ValueError("Invalid numeric quote")
            return v
        except (TypeError, ValueError):
            raise ValueError("Required broker quote field missing or invalid")
    rows = []
    totals = {}
    for entry in raw:
        item, q = entry["contract"], entry["quote"]
        depth = q.get("depth") or {}
        buy, sell = depth.get("buy") or [], depth.get("sell") or []
        if not buy or not sell:
            raise RuntimeError("Missing executable bid/ask depth")
        bid, ask = num(buy[0].get("price")), num(sell[0].get("price"))
        if bid <= 0 or ask < bid:
            raise RuntimeError("Invalid executable spread")
        oi = num(q.get("openInterest"))
        volume = num(q.get("tradeVolume"))
        key = (item["underlying"], item["expiry"])
        totals.setdefault(key, {"CE": 0, "PE": 0})[item["option_type"]] += oi
        rows.append({**item, "oi": oi, "volume": volume, "spread_pct": 200*(ask-bid)/(ask+bid), "iv_rank": None})
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
    stamp = snapshot["captured_at"]
    prediction = {"run_id": canonical_hash({"raw_snapshot_sha256": digest, "model_version": V1HeuristicModel.version}), "created_at": stamp, "mode": "PAPER", "live_order_authority": 0, "source_timestamp": stamp, "source_hash": digest, "features_hash": canonical_hash(features), "model_version": V1HeuristicModel.version, "ranking": ranking, "provenance": {"source_kind": os.environ["PHASE2_SOURCE_KIND"], "instrument_master_sha256": master_sha256, "snapshot_kind": "BROKER_QUOTE_CAPTURE_NOT_OFFICIAL_CLOSE", "pcr_scope": "SELECTED_NEAREST_EXPIRY_STRIKES_ONLY"}}
    prediction["prediction_hash"] = canonical_hash(prediction)
    receipt_path = ROOT / "data" / "paper_ledger" / "receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt = LocalArtifactPublisher(receipt_path).publish_once(prediction)
    assert receipt["prediction_hash"] == canonical_hash({k:v for k,v in prediction.items() if k != "prediction_hash"})
    print("PAPER_PREDICTION_SHA256", receipt["prediction_hash"])
    if args.push:
        if git("status", "--porcelain", "--", "data/paper_ledger/receipt.json"):
            git("add", "--", "data/paper_ledger/receipt.json")
            git("commit", "-m", "data: local read-only Angel snapshot paper receipt " + receipt["prediction_hash"])
        git("push", "origin", "HEAD:test-framework")
        print("PAPER_LEDGER_COMMIT", git("rev-parse", "HEAD"))

