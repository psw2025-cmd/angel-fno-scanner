#!/usr/bin/env python3
"""Safely classify stale/closed exchange cycles as MOCK_ONLY, never live.

Only an independently recognized source freshness or session-closure failure
may fall back to offline replay. All other scanner/runtime errors remain FAIL.
"""
import argparse
import json
import os
import subprocess
import sys
from collections import deque
from pathlib import Path

STALE_MARKERS=(
    "source timestamp out of range",
    "source exchange timestamp was not verified",
    "PAPER_SCAN_SUPPRESSED:",
)


def stale_or_holiday(lines):
    return any(marker in lines for marker in STALE_MARKERS)


def run(argv):
    recent=deque(maxlen=100)
    p=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                       text=True,errors="replace",bufsize=1)
    for line in p.stdout:
        print(line,end="",flush=True)
        recent.append(line)
    return p.wait(),"".join(recent)


def _mode(mode):
    output=os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output,"a",encoding="utf-8") as out:
            out.write(f"mode={mode}\n")


def fallback(reason):
    # Do not import actual broker credentials or mutate either production sink.
    print(f"REAL_FEED_NOT_VERIFIED: {reason}; switching to labeled MOCK_REPLAY.")
    rc,_=run([sys.executable,"-m","tools.mock_replay","--mock-replay"])
    if rc:
        return rc
    receipt=json.loads(Path("proof-output/mock_replay.json").read_text(encoding="utf-8"))
    if (receipt["mode"]!="MOCK_REPLAY" or receipt["live_verified"] is not False
        or any(receipt[k] for k in ("real_orders","broker_calls","sink_writes"))):
        raise RuntimeError("Mock-only replay not isolated from live writes")
    _mode("mock")
    print("MARKET_BOT_MOCK_ONLY_EXIT_0 (live data NOT certified)")
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock-replay-on-stale",action="store_true",required=True)
    args=parser.parse_args(argv)
    for name,value in (("PAPER_MODE","1"),("LIVE_ORDER_AUTHORITY","0"),
                       ("REAL_BROKER_ORDERS","0")):
        if os.environ.get(name,value)!=value:
            raise RuntimeError(f"Unsafe production authority: {name}")
    rc,log=run([sys.executable,"scanner.py"])
    if rc:
        if stale_or_holiday(log):
            return fallback("stale_or_closed_source")
        return rc
    rc,log=run([sys.executable,"-m","tools.check_freshness",
                "--metadata",os.getenv("ANGEL_CYCLE_METADATA_FILE","/tmp/cycle_metadata.json"),
                "--market-session",os.getenv("ANGEL_MARKET_SESSION","EOD")])
    if rc:
        if stale_or_holiday(log):
            return fallback("post_scan_exchange_tick_stale")
        return rc
    for argv in ([sys.executable,"tools/100_year_guard.py","--phase","pre",
                  "--metadata",os.getenv("ANGEL_CYCLE_METADATA_FILE","/tmp/cycle_metadata.json")],
                 [sys.executable,"agent_cli.py","--export-snapshots"],
                 [sys.executable,"scripts/sync_cycle_provenance_to_bq.py"]):
        rc,_=run(argv)
        if rc:
            return rc
    _mode("live")
    print("MARKET_BOT_LIVE_CYCLE_ACCEPTED; strict external readbacks required")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
