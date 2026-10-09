"""Read-only Angel One FULL futures quote coverage probe. No Sheets, BQ, orders or Git writes."""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

def probe():
    if os.getenv("ALLOW_PRODUCTION_WRITES") != "0":
        raise RuntimeError("read-only probe requires ALLOW_PRODUCTION_WRITES=0")
    from scanner import angel_login, discover_universe, fetch_chunked
    from tools.exchange_timestamp import get_exchange_timestamp
    api=angel_login()
    universe=discover_universe(api)
    tokens=[str(item["token"]) for item in universe.values()]
    started=time.monotonic()
    quotes, failures=fetch_chunked(api,tokens)
    latency=time.monotonic()-started
    timestamps=[]
    missing=[]
    for token in tokens:
        quote=quotes.get(token)
        if quote is None:
            missing.append(token)
            continue
        try:
            timestamps.append(datetime.fromisoformat(get_exchange_timestamp(quote)))
        except (ValueError,OverflowError,TypeError):
            missing.append(token)
    oldest=min(timestamps) if timestamps else None
    age=(datetime.now(timezone.utc)-oldest).total_seconds() if oldest else None
    verified=len(timestamps)
    result={"event":"exchange_timestamp_probe","data_source":"Angel One FULL",
        "total":len(tokens),"verified_count":verified,"missing_count":len(missing),
        "unique_tokens":len(set(tokens)),"fetch_failures":failures,
        "coverage_pct":round(100*verified/len(tokens),3) if tokens else 0,
        "oldest_exchange_timestamp":oldest.isoformat() if oldest else None,
        "oldest_age_seconds":round(age,2) if age is not None else None,
        "api_fetch_latency_seconds":round(latency,3),
        "status":"EXCHANGE_VERIFIED" if len(tokens)==219 and len(set(tokens))==219 and verified==219 and failures==0 else "SOURCE_TIME_UNVERIFIED",
        "mode":"READ_ONLY","missing_token_count":len(missing)}
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true",required=True)
    p.add_argument("--log-coverage",action="store_true")
    a=p.parse_args()
    try:
        result=probe()
    except Exception as exc:
        result={"event":"exchange_timestamp_probe","status":"PROBE_FAILED","mode":"READ_ONLY",
                "error_type":type(exc).__name__,"error":str(exc)[:300]}
    print(json.dumps(result,sort_keys=True),flush=True)
    target=Path(os.getenv("RUNNER_TEMP","/tmp"))/"probe_result.json"
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2),encoding="utf-8")
    return 0 if result["status"]=="EXCHANGE_VERIFIED" else 1

if __name__=="__main__":
    sys.exit(main())
