"""Read-only SLO evaluation for exchange tick coverage; never disables safety gates."""
import argparse
import json
from pathlib import Path

def evaluate(cycles, *, expected=219, target=0.999, consecutive_limit=3):
    results = list(cycles)
    failures = [c for c in results if c.get("verified_count") != expected or c.get("total") != expected]
    streak = 0
    for cycle in reversed(results):
        if cycle.get("verified_count") == expected and cycle.get("total") == expected:
            break
        streak += 1
    return {"cycles":len(results),"failed_cycles":len(failures),
        "coverage_slo":target,"observed_success_rate":(len(results)-len(failures))/len(results) if results else None,
        "circuit_open":streak>=consecutive_limit,"fail_closed":True}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cycles",required=True,help="JSON array of actual cycle metrics")
    args=p.parse_args()
    result=evaluate(json.loads(Path(args.cycles).read_text(encoding="utf-8")))
    print(json.dumps(result,indent=2))
    return 1 if result["circuit_open"] else 0

if __name__=="__main__":
    raise SystemExit(main())
