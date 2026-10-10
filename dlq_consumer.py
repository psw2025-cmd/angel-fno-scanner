"""Idempotent local JSONL dead-letter replay with explicit acknowledgments."""
import json
from pathlib import Path

def read_dead_letters(path):
    path=Path(path)
    if not path.exists(): return []
    entries=[]
    seen=set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():continue
        item=json.loads(line)
        key=item.get("id")
        if not key:raise ValueError("dead letter missing id")
        if key in seen:continue
        seen.add(key)
        entries.append(item)
    return entries

def replay(path,handler,ack_path):
    acknowledged=set()
    ack=Path(ack_path)
    if ack.exists():
        acknowledged=set(ack.read_text(encoding="utf-8").splitlines())
    processed=[]
    for item in read_dead_letters(path):
        if item["id"] in acknowledged:continue
        handler(item)
        with ack.open("a",encoding="utf-8") as out:
            out.write(str(item["id"])+"\n")
            out.flush()
        processed.append(item["id"])
    return processed
