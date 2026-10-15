"""Additive BigQuery schema migration. Explicit --apply and verified recovery copy required."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from phase2.option_stream import enforce_paper_mode

REQUIRED = {"cycle_id": "STRING", "data_freshness_status": "STRING", "git_sha": "STRING", "run_id": "STRING", "source_timestamp": "TIMESTAMP", "writer_id": "STRING"}

def plan(current, contract):
    current, contract = list(current), list(contract)
    names = [f["name"] for f in current]
    expected = {f["name"]: f for f in contract}
    if len(names) != len(set(names)) or len(expected) != 54 or len(contract) != 54:
        raise ValueError("Duplicate fields or invalid 54-column contract")
    existing = {f["name"]: f for f in current}
    for name, field in existing.items():
        if name not in expected:
            raise ValueError("Unexpected field: " + name)
        target = expected[name]
        if field["type"].upper() != target["type"].upper() or field.get("mode", "NULLABLE") != target.get("mode", "NULLABLE"):
            raise ValueError("Incompatible field: " + name)
    for name, kind in REQUIRED.items():
        if expected[name]["type"] != kind or expected[name].get("mode") != "NULLABLE":
            raise ValueError("Invalid contract: " + name)
    return {"status": "PLAN_ONLY", "missing": [f for f in contract if f["name"] not in existing], "existing_columns": len(current), "target_columns": 54}

def migrate(table_id, backup_id, *, apply=False, writers_quiesced=False, client=None):
    enforce_paper_mode()
    from google.cloud import bigquery
    client = client or bigquery.Client()
    table = client.get_table(table_id)
    contract = json.loads((Path(__file__).resolve().parents[1] / "schemas/option_predictions_live.json").read_text())
    def fields(t):
        return [{"name": f.name, "type": f.field_type, "mode": f.mode} for f in t.schema]
    result = plan(fields(table), contract)
    result.update(table=table_id, backup=backup_id, apply=apply)
    if not apply:
        return result
    if not writers_quiesced or table_id == backup_id or table.location != client.get_dataset(backup_id.rsplit(".", 1)[0]).location:
        raise RuntimeError("Writer quiescence, distinct backup and matching dataset locations required")
    if not backup_id.startswith(table_id.rsplit(".", 1)[0] + "."):
        raise RuntimeError("Backup must be in source dataset")
    before_count = next(iter(client.query("SELECT COUNT(*) AS n FROM `" + table_id + "`").result())).n
    job = client.copy_table(table_id, backup_id, job_config=bigquery.CopyJobConfig(write_disposition="WRITE_EMPTY"))
    job.result()
    backup_count = next(iter(client.query("SELECT COUNT(*) AS n FROM `" + backup_id + "`").result())).n
    if backup_count != before_count:
        raise RuntimeError("Recovery copy count mismatch; production unchanged")
    current = client.get_table(table_id)
    plan(fields(current), contract)
    missing = {f["name"] for f in result["missing"]}
    additions = [bigquery.SchemaField(f["name"], f["type"], mode="NULLABLE") for f in contract if f["name"] in missing]
    if additions:
        current.schema = list(current.schema) + additions
        client.update_table(current, ["schema"])
    final = client.get_table(table_id)
    if plan(fields(final), contract)["missing"]:
        raise RuntimeError("Post-migration schema incomplete")
    after_count = next(iter(client.query("SELECT COUNT(*) AS n FROM `" + table_id + "`").result())).n
    if before_count != after_count:
        raise RuntimeError("Post-migration row count mismatch")
    result.update(status="SCHEMA_APPLIED_AND_COUNT_VERIFIED", rows_before=before_count, rows_after=after_count, backup_rows=backup_count, verified_at=datetime.now(timezone.utc).isoformat())
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--backup", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-quiesced", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(args.table, args.backup, apply=args.apply, writers_quiesced=args.writers_quiesced), indent=2))
