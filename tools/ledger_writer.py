"""Durable idempotent append-only cycle ledger."""
import json
import os
from pathlib import Path

def append_cycle(path, cycle):
    required = {"cycle_id", "run_id", "git_sha", "status", "ts"}
    if not required.issubset(cycle):
        raise ValueError("missing cycle fields: " + str(sorted(required - cycle.keys())))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = (str(cycle["cycle_id"]), str(cycle["run_id"]))
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            existing = json.loads(line)
            if (str(existing.get("cycle_id")), str(existing.get("run_id"))) == key:
                if existing != cycle:
                    raise ValueError("conflicting immutable cycle")
                return False
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(cycle, sort_keys=True, ensure_ascii=True) + "\n")
        out.flush()
        os.fsync(out.fileno())
    return True
