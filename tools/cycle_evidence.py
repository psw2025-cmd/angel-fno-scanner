"""Conservative cross-system identity gate: missing evidence is failure, not local MATCH."""
import json
from pathlib import Path

REQUIRED = ("run_id", "git_sha", "cycle_id", "writer_id", "source_timestamp")

def compare_cycle_evidence(metadata, *, sheets=None, bigquery=None, git=None):
    if not all(metadata.get(k) for k in REQUIRED):
        return False, "missing authoritative cycle metadata"
    sources = {"Sheets": sheets, "BigQuery": bigquery, "Git": git}
    for source, evidence in sources.items():
        if not isinstance(evidence, dict):
            return False, f"{source} evidence unavailable"
        for key in REQUIRED:
            if not evidence.get(key) or str(evidence[key]) != str(metadata[key]):
                return False, f"{source} {key} mismatch or missing"
    return True, "MATCH: cross-system cycle identity"

def verify_atomic_cycle(metadata_file, *, sheets=None, bigquery=None, git=None):
    with open(metadata_file, encoding="utf-8") as f:
        metadata = json.load(f)
    return compare_cycle_evidence(metadata, sheets=sheets, bigquery=bigquery, git=git)
