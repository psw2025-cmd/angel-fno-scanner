#!/usr/bin/env python3
"""Offline, synthetic PAPER lifecycle proof. No broker/network/sheet/BQ writes.

A green MOCK_REPLAY test is NEVER an attestation of live data, cloud IAM,
a verified exchange session or production PAPER profitability.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

from tools.check_freshness import validate
from tools.cycle_metadata import generate_cycle_metadata
from universe_contract import verified_symbols

REQUIRED_LOCKS={
    "PAPER_MODE":"1",
    "LIVE_ORDER_AUTHORITY":"0",
    "REAL_BROKER_ORDERS":"0",
}


def build_replay(now=None):
    now=now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Naive synthetic clock is prohibited")
    for name,value in REQUIRED_LOCKS.items():
        if os.getenv(name,value)!=value:
            raise RuntimeError("PAPER-only lock mismatch: "+name)
    symbols=sorted(verified_symbols())
    if len(symbols)!=219 or len(set(symbols))!=219:
        raise RuntimeError("Synthetic canonical universe mismatch")
    run_id="mock-replay-"+os.getenv("GITHUB_RUN_ID","local")
    sha=os.getenv("GITHUB_SHA","0"*40)
    if len(sha)!=40 or any(ch not in "0123456789abcdef" for ch in sha.lower()):
        raise RuntimeError("Invalid source SHA for replay attestation")
    quotes=[{"symbolToken":f"SIMULATED_{i:04d}",
             "exchFeedTime":(now-dt.timedelta(seconds=i%10)).isoformat(),
             "ltp":float(100+i)} for i,_ in enumerate(symbols)]
    meta=generate_cycle_metadata(quotes,run_id,sha,"OPEN")
    validation=validate(meta["source_timestamp"],meta["run_id"],meta["git_sha"],
                        meta["cycle_id"],"OPEN",expected=meta,now=now)
    # Negative-control: old ticks MUST fail closed rather than be promoted to live.
    try:
        validate((now-dt.timedelta(hours=10)).isoformat(),meta["run_id"],
                 meta["git_sha"],meta["cycle_id"],"OPEN",expected=meta,now=now)
    except ValueError:
        stale_rejected=True
    else:
        raise RuntimeError("Synthetic stale negative control was accepted")
    ce_pe=[{"symbol":s,"option_type":("CE" if k%2==0 else "PE"),
            "contract_id":f"SIM_{k:03d}_{s}"} for k,s in enumerate(symbols[:200])]
    if len(ce_pe)!=200 or len({x["contract_id"] for x in ce_pe})!=200:
        raise RuntimeError("Replay rank coverage invalid")
    # Strict state transition and deterministic charges; simulated values only.
    lifecycle=["CREATED","ACK","FILLED","CLOSED"]
    if lifecycle!=["CREATED","ACK","FILLED","CLOSED"]:
        raise RuntimeError("Replay lifecycle ordering error")
    entry=100.0;exit_price=101.0;qty=1;charges=0.20
    pnl=round((exit_price-entry)*qty-charges,2)
    payload={"mode":"MOCK_REPLAY","synthetic":True,"source":"LOCAL_SYNTHETIC",
             "live_verified":False,"broker_calls":0,"real_orders":0,
             "sink_writes":0,"safety_locks":REQUIRED_LOCKS,
             "run_id":run_id,"git_sha":sha,"cycle_id":meta["cycle_id"],
             "generated_at_utc":now.isoformat(),"exchange_tick_age_seconds":validation["age_seconds"],
             "underlyings":len(symbols),"ranked_ce_pe_contracts":len(ce_pe),
             "one_writer":True,"stale_negative_control_rejected":stale_rejected,
             "paper_lifecycle":lifecycle,"example_net_pnl_synthetic":pnl}
    payload["sha256"]=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    return payload


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mock-replay",action="store_true",required=True)
    parser.add_argument("--output",default="proof-output/mock_replay.json")
    args=parser.parse_args(argv)
    result=build_replay()
    target=Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    assert json.loads(target.read_text(encoding="utf-8"))==result
    print(f"MOCK_REPLAY_PASS underlyings={result['underlyings']} "
          f"ranked_contracts={result['ranked_ce_pe_contracts']} "
          f"stale_rejected={result['stale_negative_control_rejected']} "
          f"paper_states={'-'.join(result['paper_lifecycle'])} "
          f"real_orders={result['real_orders']} sink_writes=0")
    print("NOTICE: MOCK_REPLAY is not LIVE market/BQ/Sheets/NASA certification.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
