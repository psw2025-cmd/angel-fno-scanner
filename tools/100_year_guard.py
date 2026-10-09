"""Fail-closed cycle contract guard; pre and post are distinct gates."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from check_freshness import validate

def verify(meta, phase, root=Path("."), *, now=None, expected=219):
    if meta.get("data_freshness_status") != "EXCHANGE_VERIFIED":
        raise ValueError("exchange provenance not verified")
    if meta.get("verified_count") != expected or meta.get("total") != expected:
        raise ValueError("exchange coverage mismatch")
    validate(meta.get("source_timestamp"), meta.get("run_id"), meta.get("git_sha"),
             meta.get("cycle_id"), meta.get("market_session"), expected=meta, now=now)
    if phase == "post":
        for name, count in (("universe.csv", expected), ("ranked.csv", 200)):
            path = root / "scratch" / "snapshots" / name
            if not path.is_file():
                raise ValueError(f"missing published snapshot: {name}")
            with path.open(encoding="utf-8-sig", newline="") as f:
                actual = sum(1 for row in csv.DictReader(f) if any(str(v).strip() for v in row.values() if v is not None))
            if actual != count:
                raise ValueError(f"{name} count mismatch {actual}/{count}")
        # External sinks cannot be marked PASS without authenticated reads.
        raise ValueError("post-check requires independent Sheets and BigQuery readback and hash reconciliation")
    return {"status":"PASS", "phase":phase, "run_id":str(meta["run_id"]), "verified":expected}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--phase",choices=("pre","post"),required=True)
    p.add_argument("--metadata",required=True)
    p.add_argument("--root",default=".")
    a=p.parse_args()
    try:
        result=verify(json.loads(Path(a.metadata).read_text(encoding="utf-8")),a.phase,Path(a.root))
        print(json.dumps(result));return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps({"status":"FAIL_CLOSED","phase":a.phase,"reason":str(e)}));return 1
if __name__=="__main__":
    raise SystemExit(main())
