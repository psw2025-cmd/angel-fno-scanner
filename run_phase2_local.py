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
    if not manifest_path.is_file():
        raise RuntimeError("Missing locally verified Angel option-contract manifest: " + str(manifest_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("Manifest must be a nonempty JSON list")
    keys = set()
    for item in manifest:
        if item.get("underlying") not in ("NIFTY", "BANKNIFTY") or item.get("option_type") not in ("CE", "PE") or item.get("exchange") != "NFO":
            raise ValueError("Invalid contract manifest identity")
        if not all(item.get(k) for k in ("tradingsymbol", "symboltoken", "expiry", "strike")):
            raise ValueError("Missing contract mapping")
        key = (item["underlying"], item["expiry"], item["strike"], item["option_type"])
        if key in keys:
            raise ValueError("Duplicate contract mapping")
        keys.add(key)
    if {x["underlying"] for x in manifest} != {"NIFTY", "BANKNIFTY"} or {x["option_type"] for x in manifest} != {"CE", "PE"}:
        raise ValueError("Both underlyings and CE/PE required")
    broker = AngelReadOnlyProvider()
    raw = []
    for item in manifest:
        quote = broker.quote("NFO", item["tradingsymbol"], item["symboltoken"])
        if quote.get("tradingSymbol") != item["tradingsymbol"]:
            raise RuntimeError("Quote trading symbol mismatch")
        raw.append({"contract": item, "quote": quote})
    # Broker FULL quotes alone do not establish a complete, time-aligned option chain,
    # per-contract PCR, executable bid/ask and official close. Never manufacture these.
    snapshot = {"source_kind": os.environ["PHASE2_SOURCE_KIND"], "captured_at": datetime.now(IST).isoformat(), "quotes": raw}
    raw_path = ROOT / "data" / "raw_snapshot.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(snapshot, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    print("REAL_BROKER_RAW_SNAPSHOT_SHA256", digest)
    raise RuntimeError("Raw broker quotes captured locally, but certified close requires verified complete chain, timestamp, bid/ask and observed PCR; no prediction/receipt or push performed.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PHASE2_FAIL_CLOSED:", exc, file=sys.stderr)
        sys.exit(1)
