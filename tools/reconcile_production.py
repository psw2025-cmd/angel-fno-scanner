"""Read-only, evidence-based local snapshot reconciliation; no fabricated production MATCH."""
import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def count_csv(path):
    if not path.is_file():
        return None
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return sum(1 for row in csv.DictReader(handle) if any(str(v).strip() for v in row.values() if v is not None))

def reconcile(meta, root=ROOT):
    run_id = str(meta.get("run_id", ""))
    provenance = root / "scratch" / "provenance" / f"{run_id}.json"
    universe = count_csv(root / "scratch" / "snapshots" / "universe.csv")
    ranked = count_csv(root / "scratch" / "snapshots" / "ranked.csv")
    reasons = []
    if meta.get("data_freshness_status") != "EXCHANGE_VERIFIED" or meta.get("verified_count") != 219:
        reasons.append("exchange coverage not verified")
    if not provenance.is_file():
        reasons.append("local provenance missing")
    else:
        actual = json.loads(provenance.read_text(encoding="utf-8"))
        if any(str(actual.get(k)) != str(meta.get(k)) for k in ("run_id", "git_sha", "cycle_id", "source_timestamp")):
            reasons.append("local provenance mismatch")
    if universe != 219 or ranked != 200:
        reasons.append("local snapshot count mismatch or files missing")
    return {"status":"LOCAL_ONLY" if not reasons else "FAIL", "universe_actual":universe,
        "universe_expected":219,"ranked_actual":ranked,"ranked_expected":200,
        "sheets":"NOT_VERIFIED", "bigquery":"NOT_VERIFIED", "git":"NOT_VERIFIED",
        "reasons":reasons}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-id", required=True)
    p.add_argument("--sha", required=True)
    p.add_argument("--metadata", required=True)
    p.add_argument("--local-check", action="store_true")
    args=p.parse_args()
    try:
        meta=json.loads(Path(args.metadata).read_text(encoding="utf-8"))
        if str(meta.get("run_id")) != args.run_id or str(meta.get("git_sha")) != args.sha:
            raise ValueError("requested run_id or SHA does not match metadata")
        result=reconcile(meta)
        print(json.dumps(result,indent=2))
        return 0 if args.local_check and result["status"]=="LOCAL_ONLY" else 1
    except Exception as exc:
        print(json.dumps({"status":"FAIL","reason":str(exc)}))
        return 1

if __name__=="__main__":
    sys.exit(main())
