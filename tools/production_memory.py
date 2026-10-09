"""Summarize historical repository failure patterns and current-cycle freshness risk."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

KEYWORDS=("snapshot","freshness","stale","atomic","push fail","provenance")
def analyze_history(repo="."):
    log=subprocess.check_output(["git","-C",repo,"log","-100","--format=%h %s"],text=True,encoding="utf-8",errors="replace")
    return [line for line in log.splitlines() if any(k in line.lower() for k in KEYWORDS)]

def predict(metadata, *, now=None):
    if not metadata:
        return {"status":"NO_LIVE_METADATA","decision":"BLOCK"}
    if metadata.get("data_freshness_status")!="EXCHANGE_VERIFIED":
        return {"status":"UNVERIFIED","decision":"BLOCK"}
    stamp=datetime.fromisoformat(metadata["source_timestamp"].replace("Z","+00:00"))
    if stamp.tzinfo is None:
        return {"status":"NAIVE_TIMESTAMP","decision":"BLOCK"}
    age=((now or datetime.now(timezone.utc))-stamp).total_seconds()
    threshold=120 if metadata.get("market_session")=="OPEN" else 3600
    return {"oldest_age_seconds":round(age,2),"warning":age>threshold*0.8,
        "decision":"BLOCK" if age< -30 or age>threshold else "ELIGIBLE_FOR_OTHER_GATES"}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--analyze-past",action="store_true")
    p.add_argument("--probe-present",action="store_true")
    p.add_argument("--predict-future",action="store_true")
    p.add_argument("--metadata")
    a=p.parse_args()
    meta=json.loads(Path(a.metadata).read_text(encoding="utf-8")) if a.metadata else None
    result={"past_commit_matches":analyze_history() if a.analyze_past else [],
        "present":"NOT_PROBED" if a.probe_present else "NOT_REQUESTED",
        "future_risk":predict(meta) if a.predict_future else "NOT_REQUESTED"}
    print(json.dumps(result,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
