"""Align option_predictions_live with the committed contract without a truncate.

The live table drifted: source_timestamp is STRING, and cycle_id plus
data_freshness_status are absent. WRITE_TRUNCATE must not retype or invent
those columns. This planner only allows a retype when source_timestamp is
empty, then adds the two missing nullable strings.

The apply path copies the table first, tries the change on the copy, and
only then changes the live table.
"""
from __future__ import annotations

import datetime as dt

PROJECT = "fno-angel-prod-1790444589"
DATASET = "fno_predictions"
TABLE = "option_predictions_live"


class SchemaRepairError(RuntimeError):
    """Raised when the live table cannot be aligned safely."""


def plan_repairs(column_types, nonempty_source_timestamp):
    """Return ordered repair steps. An empty list means the table already matches."""
    types = dict(column_types or {})
    source = types.get("source_timestamp")
    steps = []
    if source == "STRING":
        if int(nonempty_source_timestamp) != 0:
            raise SchemaRepairError(
                "source_timestamp holds values; refusing a blind retype"
            )
        # BigQuery will not ALTER STRING to TIMESTAMP, even when every value is null.
        # Dropping the empty column and adding a TIMESTAMP column keeps every row.
        steps.append(("drop_column", "source_timestamp", ""))
        steps.append(("add_column", "source_timestamp", "TIMESTAMP"))
    elif source != "TIMESTAMP":
        raise SchemaRepairError(f"source_timestamp is {source or 'missing'}")
    if "cycle_id" not in types:
        steps.append(("add_column", "cycle_id", "STRING"))
    elif types["cycle_id"] != "STRING":
        raise SchemaRepairError(f"cycle_id is {types['cycle_id']}, expected STRING")
    if "data_freshness_status" not in types:
        steps.append(("add_column", "data_freshness_status", "STRING"))
    elif types["data_freshness_status"] != "STRING":
        raise SchemaRepairError(
            f"data_freshness_status is {types['data_freshness_status']}, expected STRING"
        )
    return steps


def _qualified(name):
    return f"`{PROJECT}.{DATASET}.{name}`"


def _sql_for(table_name, step):
    kind, column, type_name = step
    target = _qualified(table_name)
    if kind == "drop_column":
        if column != "source_timestamp":
            raise SchemaRepairError("only an empty source_timestamp column may be dropped")
        return f"ALTER TABLE {target} DROP COLUMN {column}"
    if kind == "add_column":
        return f"ALTER TABLE {target} ADD COLUMN {column} {type_name}"
    raise SchemaRepairError(f"unknown repair step {kind}")


def _column_types(client, table_name):
    query = f"""
        SELECT column_name, data_type
        FROM `{PROJECT}.{DATASET}.INFORMATION_SCHEMA.COLUMNS`
        WHERE table_name = @table_name
    """
    from google.cloud import bigquery
    job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("table_name", "STRING", table_name)]
        ),
    )
    return {row.column_name: row.data_type for row in job.result()}


def _count(client, table_name):
    rows = list(client.query(f"SELECT COUNT(*) AS n FROM {_qualified(table_name)}").result())
    return int(rows[0].n)


def apply_repairs(client, now=None):
    """Back up, prove the change on a copy, then alter the live table.

    Returns a dict of evidence. Does not drop the backup.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    backup = f"{TABLE}_backup_{stamp}_schema_repair"
    scratch = f"{TABLE}_scratch_{stamp}_schema_repair"
    types = _column_types(client, TABLE)
    nonempty_rows = list(client.query(
        f"SELECT COUNTIF(source_timestamp IS NOT NULL) AS n FROM {_qualified(TABLE)}"
    ).result())
    nonempty = int(nonempty_rows[0].n)
    before_count = _count(client, TABLE)
    steps = plan_repairs(types, nonempty)
    if not steps:
        return {
            "changed": False,
            "before_count": before_count,
            "steps": [],
            "source_timestamp": types.get("source_timestamp"),
        }
    client.query(f"CREATE TABLE {_qualified(backup)} CLONE {_qualified(TABLE)}").result()
    client.query(f"CREATE TABLE {_qualified(scratch)} CLONE {_qualified(TABLE)}").result()
    backup_count = _count(client, backup)
    scratch_count = _count(client, scratch)
    if backup_count != before_count or scratch_count != before_count:
        raise SchemaRepairError(
            f"backup count mismatch live={before_count} backup={backup_count} scratch={scratch_count}"
        )
    for step in steps:
        client.query(_sql_for(scratch, step)).result()
    scratch_types = _column_types(client, scratch)
    if scratch_types.get("source_timestamp") != "TIMESTAMP":
        raise SchemaRepairError("scratch source_timestamp did not become TIMESTAMP")
    if scratch_types.get("cycle_id") != "STRING" or scratch_types.get("data_freshness_status") != "STRING":
        raise SchemaRepairError("scratch is missing a required string column")
    if _count(client, scratch) != before_count:
        raise SchemaRepairError("scratch row count changed")
    for step in steps:
        client.query(_sql_for(TABLE, step)).result()
    after_types = _column_types(client, TABLE)
    after_count = _count(client, TABLE)
    if after_count != before_count:
        raise SchemaRepairError(f"live row count changed from {before_count} to {after_count}")
    if after_types.get("source_timestamp") != "TIMESTAMP":
        raise SchemaRepairError("live source_timestamp is not TIMESTAMP after repair")
    client.query(f"DROP TABLE {_qualified(scratch)}").result()
    return {
        "changed": True,
        "before_count": before_count,
        "after_count": after_count,
        "backup": backup,
        "steps": [f"{kind} {column} {type_name}" for kind, column, type_name in steps],
        "source_timestamp": after_types.get("source_timestamp"),
        "cycle_id": after_types.get("cycle_id"),
        "data_freshness_status": after_types.get("data_freshness_status"),
        "nonempty_source_timestamp_before": nonempty,
    }
