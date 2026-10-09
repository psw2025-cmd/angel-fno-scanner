"""CI regression guard for authoritative timestamp, atomic publication and 219 coverage."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"docs"/"permanent_failure_memory.json"
REQUIRED={
    "tools/cycle_metadata.py":("generate_cycle_metadata","expected_quotes=219","oldest_exchange_timestamp"),
    "tools/exchange_timestamp.py":("exchFeedTime","oldest_exchange_timestamp"),
    "tools/check_freshness.py":("120 if market_session", "3600","source_timestamp"),
    "tools/atomic_snapshots.py":("publish_bundle","replace","backup"),
    "scanner.py":("generate_cycle_metadata","ANGEL_REQUIRE_EXCHANGE_TIME"),
    ".github/workflows/market_bot.yml":("ANGEL_CYCLE_METADATA_FILE","check_freshness.py","probe_angel_live.py"),
}
def validate(root=ROOT):
    memory=json.loads((root/"docs"/"permanent_failure_memory.json").read_text(encoding="utf-8"))
    if memory.get("defect_id")!="240dfb2-37891229917":
        raise ValueError("permanent defect ID changed")
    for filename,markers in REQUIRED.items():
        content=(root/filename).read_text(encoding="utf-8")
        for marker in markers:
            if marker not in content:
                raise ValueError(f"regression: {filename} missing {marker}")
    return {"status":"PASS","guarded_files":len(REQUIRED)}
if __name__=="__main__":
    print(json.dumps(validate()))
