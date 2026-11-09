"""Add missing nullable provenance fields without truncating or rewriting BigQuery rows.

This is an explicit, one-shot operator repair. It does not run during scanning.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from google.cloud import bigquery

PROJECT = "fno-angel-prod-1790444589"
TABLE = f"{PROJECT}.fno_predictions.option_predictions_live"
REQUIRED = ("run_id", "git_sha", "writer_id", "source_timestamp", "cycle_id")


def main():
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY", "0") != "0" or os.getenv("REAL_BROKER_ORDERS", "0") != "0":
        raise RuntimeError("PAPER-only safety lock missing")
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "option_predictions_live.json"
    canonical = {x["name"]: x for x in json.loads(schema_path.read_text(encoding="utf-8"))}
    client = bigquery.Client(project=PROJECT)
    table = client.get_table(TABLE)
    existing = {f.name: f for f in table.schema}
    missing = [name for name in REQUIRED if name not in existing]
    for name in REQUIRED:
        if name in existing and existing[name].field_type.upper() != canonical[name]["type"].upper():
            raise RuntimeError(f"Unsafe type mismatch for {name}: {existing[name].field_type}")
    if not missing:
        print("PASS: BigQuery provenance schema already complete; no changes")
        return
    additions = []
    for name in missing:
        definition = canonical[name]
        if definition["mode"] != "NULLABLE":
            raise RuntimeError(f"Refusing non-nullable schema change: {name}")
        additions.append(bigquery.SchemaField(name, definition["type"], mode="NULLABLE"))
    table.schema = list(table.schema) + additions
    client.update_table(table, ["schema"])
    verified = client.get_table(TABLE)
    assert all(name in {f.name for f in verified.schema} for name in REQUIRED)
    print("PASS: BigQuery additive schema repair:", ",".join(missing), "no row rewrite")


if __name__ == "__main__":
    main()
