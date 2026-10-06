"""Read-only provenance verification across Angel F&O BigQuery tables.

This module MUST NOT mutate BigQuery. It verifies that the current authoritative
option_predictions_live cycle has complete lineage and checks auxiliary rows
that reference the same cycle.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google.cloud import bigquery

from angel_prediction_engine import BQ_DATASET_ID, get_bigquery_client

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = BQ_DATASET_ID
PROVENANCE_FIELDS = ("run_id", "git_sha", "writer_id", "source_timestamp", "cycle_id")


def _quoted(table_name: str) -> str:
    b = chr(96)
    return f"{b}{PROJECT_ID}.{DATASET_ID}.{table_name}{b}"


def _schema_names(client, table_name):
    table = client.get_table(f"{PROJECT_ID}.{DATASET_ID}.{table_name}")
    return {field.name for field in table.schema}


def verify_cycle_provenance():
    client = get_bigquery_client()
    option_table = _quoted("option_predictions_live")
    ref_sql = f"""
    SELECT
      COUNT(*) AS total_rows,
      COUNT(DISTINCT symbol) AS unique_symbols,
      ANY_VALUE(run_id) AS run_id,
      ANY_VALUE(git_sha) AS git_sha,
      ANY_VALUE(writer_id) AS writer_id,
      CAST(MAX(source_timestamp) AS STRING) AS source_timestamp,
      ANY_VALUE(cycle_id) AS cycle_id,
      COUNT(DISTINCT run_id) AS run_ids,
      COUNT(DISTINCT git_sha) AS git_shas,
      COUNT(DISTINCT writer_id) AS writer_ids,
      COUNT(DISTINCT cycle_id) AS cycle_ids,
      COUNTIF(run_id IS NULL OR git_sha IS NULL OR writer_id IS NULL OR
              source_timestamp IS NULL OR cycle_id IS NULL) AS missing_lineage
    FROM {option_table}
    """
    ref = list(client.query(ref_sql).result())[0]
    identity = {
        "run_id": ref.run_id,
        "git_sha": ref.git_sha,
        "writer_id": ref.writer_id,
        "cycle_id": ref.cycle_id,
        "source_timestamp": ref.source_timestamp,
    }
    problems = []
    if ref.total_rows != 219 or ref.unique_symbols != 219:
        problems.append(
            f"option_predictions_live universe={ref.unique_symbols}/{ref.total_rows}, expected 219/219"
        )
    if ref.missing_lineage:
        problems.append(f"option_predictions_live missing lineage rows={ref.missing_lineage}")
    if any(v != 1 for v in (ref.run_ids, ref.git_shas, ref.writer_ids, ref.cycle_ids)):
        problems.append("option_predictions_live contains mixed provenance")
    if any(not identity[k] for k in ("run_id", "git_sha", "writer_id", "cycle_id")):
        problems.append("option_predictions_live identity is incomplete")

    auxiliaries = {}
    for table_name in ("market_news_sentiment", "prediction_calibration_log", "next_day_gap_predictions"):
        names = _schema_names(client, table_name)
        missing_cols = [f for f in PROVENANCE_FIELDS if f not in names]
        if missing_cols:
            problems.append(f"{table_name} missing provenance columns: {missing_cols}")
            auxiliaries[table_name] = {"missing_columns": missing_cols}
            continue

        sql = f"""
        SELECT
          COUNT(*) AS rows_for_cycle,
          COUNTIF(run_id != @run_id OR git_sha != @git_sha OR writer_id != @writer_id) AS mismatched_rows
        FROM {_quoted(table_name)}
        WHERE cycle_id = @cycle_id
        """
        cfg = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("run_id", "STRING", identity["run_id"]),
                bigquery.ScalarQueryParameter("git_sha", "STRING", identity["git_sha"]),
                bigquery.ScalarQueryParameter("writer_id", "STRING", identity["writer_id"]),
                bigquery.ScalarQueryParameter("cycle_id", "STRING", identity["cycle_id"]),
            ]
        )
        row = list(client.query(sql, job_config=cfg).result())[0]
        auxiliaries[table_name] = {
            "rows_for_cycle": row.rows_for_cycle,
            "mismatched_rows": row.mismatched_rows,
        }
        if row.mismatched_rows:
            problems.append(
                f"{table_name} has {row.mismatched_rows} provenance mismatches for current cycle"
            )

    cal = auxiliaries.get("prediction_calibration_log", {})
    if cal.get("rows_for_cycle", 0) < 1:
        problems.append("prediction_calibration_log has no row for the current cycle")

    result = {
        "status": "PASS" if not problems else "FAIL",
        "identity": identity,
        "option_predictions_live": {
            "total_rows": ref.total_rows,
            "unique_symbols": ref.unique_symbols,
            "missing_lineage": ref.missing_lineage,
        },
        "auxiliary_tables": auxiliaries,
        "problems": problems,
        "read_only": True,
    }
    print(json.dumps(result, indent=2, default=str))
    if problems:
        raise SystemExit(1)
    return result


if __name__ == "__main__":
    verify_cycle_provenance()
