"""Read-only production migration planner; never changes cloud resources."""
import argparse
import json
from pathlib import Path

REQUIRED = {"cycle_id": "STRING", "data_freshness_status": "STRING", "git_sha": "STRING", "run_id": "STRING", "source_timestamp": "TIMESTAMP", "writer_id": "STRING"}

def plan(current, contract):
    current = list(current)
    contract = list(contract)
    names = [f["name"] for f in current]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate production fields")
    expected = {f["name"]: f for f in contract}
    if len(expected) != 54 or len(contract) != 54:
        raise ValueError("Expected exactly 54 unique contract fields")
    existing = {f["name"]: f for f in current}
    for name, field in existing.items():
        if name not in expected:
            raise ValueError("Unexpected production field: " + name)
        target = expected[name]
        if field["type"].upper() != target["type"].upper() or field.get("mode", "NULLABLE") != target.get("mode", "NULLABLE"):
            raise ValueError("Incompatible existing field: " + name)
    for name, kind in REQUIRED.items():
        if expected[name]["type"] != kind or expected[name].get("mode") != "NULLABLE":
            raise ValueError("Invalid six-column contract: " + name)
    return {"status": "PLAN_ONLY", "missing": [f for f in contract if f["name"] not in existing], "existing_columns": len(current), "target_columns": 54,
            "release_gates": ["writer quiescence", "consistent backup and restore rehearsal", "row identity reconciliation", "authorized additive schema update", "post-update independent verification"]}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--current-schema-json", required=True)
    args = p.parse_args()
    contract = json.loads((Path(__file__).resolve().parents[1] / "schemas/option_predictions_live.json").read_text())
    print(json.dumps(plan(json.loads(Path(args.current_schema_json).read_text()), contract), indent=2))
