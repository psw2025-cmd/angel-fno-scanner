"""
tools/export_cloud_database.py

Permanent utility to extract all datasets, tables, schemas, and rows from
Google Cloud BigQuery into a single portable file (SQLite database, consolidated JSON, or ZIP).

Usage:
    python tools/export_cloud_database.py                     # Exports all tables to SQLite (.db) and JSON
    python tools/export_cloud_database.py --format sqlite     # Exports to single SQLite .db file
    python tools/export_cloud_database.py --format json       # Exports to single consolidated JSON file
    python tools/export_cloud_database.py --format zip        # Exports to single ZIP archive of CSVs
    python tools/export_cloud_database.py --format all        # Generates all single-file formats
    python tools/export_cloud_database.py --output-file C:/path/to/my_export.db
"""

from __future__ import annotations

import argparse
import csv
import datetime
import io
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_PROJECT_ID = "fno-angel-prod-1790444589"
DEFAULT_DATASET_ID = "fno_predictions"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "audit" / "cloud_exports"


def get_bq_client(project_id: str | None = None):
    """Obtain authenticated BigQuery client using project's credential hierarchy."""
    try:
        from angel_prediction_engine import get_bigquery_client
        return get_bigquery_client()
    except Exception as exc:
        try:
            from google.cloud import bigquery
            proj = project_id or os.environ.get("BQ_PROJECT_ID") or DEFAULT_PROJECT_ID
            return bigquery.Client(project=proj)
        except Exception as e2:
            raise RuntimeError(
                f"Failed to initialize BigQuery client: {exc} | Direct fallback error: {e2}"
            ) from e2


def map_bq_type_to_sqlite(bq_type: str) -> str:
    """Map BigQuery data type to corresponding SQLite data type."""
    t = bq_type.upper()
    if t in ("INT64", "INTEGER", "INT", "SMALLINT", "TINYINT", "BIGINT"):
        return "INTEGER"
    if t in ("FLOAT64", "FLOAT", "NUMERIC", "BIGNUMERIC", "DECIMAL"):
        return "REAL"
    if t in ("BOOL", "BOOLEAN"):
        return "INTEGER"
    if t in ("BYTES",):
        return "BLOB"
    # STRING, TIMESTAMP, DATETIME, DATE, TIME, GEOGRAPHY, JSON, RECORD, STRUCT, ARRAY
    return "TEXT"


def sanitize_val_for_sqlite(val: Any) -> Any:
    """Normalize BigQuery row value for insertion into SQLite."""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, (dict, list)):
        return json.dumps(val, default=str)
    if isinstance(val, bytes):
        return val
    if isinstance(val, bool):
        return 1 if val else 0
    return val


def sanitize_val_for_json(val: Any) -> Any:
    """Normalize BigQuery row value for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, (datetime.datetime, datetime.date, datetime.time)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return val


def fetch_dataset_tables(
    bq_client, dataset_id: str, include_backups: bool = True
) -> list[str]:
    """List all table IDs in the dataset."""
    tables = [t.table_id for t in bq_client.list_tables(dataset_id)]
    if not include_backups:
        tables = [t for t in tables if "_backup_" not in t]
    return sorted(tables)


def extract_table_data(
    bq_client, project_id: str, dataset_id: str, table_id: str
) -> dict[str, Any]:
    """
    Extract schema, metadata, and all rows for a single BigQuery table.
    Returns structured dictionary with schema, columns, metadata, and rows.
    """
    table_ref = f"{project_id}.{dataset_id}.{table_id}"
    bq_table = bq_client.get_table(table_ref)

    columns_info = [
        {
            "name": field.name,
            "type": field.field_type,
            "mode": field.mode,
            "description": field.description or "",
        }
        for field in bq_table.schema
    ]

    col_names = [f["name"] for f in columns_info]

    # Query all rows ordered if source_timestamp or timestamp exists
    has_source_ts = "source_timestamp" in col_names
    has_ts = "timestamp" in col_names
    has_date = "prediction_date" in col_names

    order_clause = ""
    if has_source_ts:
        order_clause = " ORDER BY source_timestamp ASC NULLS LAST"
    elif has_ts:
        order_clause = " ORDER BY timestamp ASC NULLS LAST"
    elif has_date:
        order_clause = " ORDER BY prediction_date ASC NULLS LAST"

    query = f"SELECT * FROM `{table_ref}`{order_clause}"
    query_job = bq_client.query(query)
    rows_iterator = query_job.result()

    rows: list[dict[str, Any]] = []
    for r in rows_iterator:
        row_dict = {}
        for col in col_names:
            row_dict[col] = r.get(col)
        rows.append(row_dict)

    return {
        "table_id": table_id,
        "full_table_id": table_ref,
        "num_rows": bq_table.num_rows,
        "num_bytes": bq_table.num_bytes,
        "created": bq_table.created.isoformat() if bq_table.created else None,
        "modified": bq_table.modified.isoformat() if bq_table.modified else None,
        "description": bq_table.description or "",
        "columns": columns_info,
        "rows": rows,
    }


def write_to_sqlite(
    extracted_tables: list[dict[str, Any]],
    output_path: Path,
    project_id: str,
    dataset_id: str,
    now_utc: datetime.datetime,
    now_ist: datetime.datetime,
) -> int:
    """
    Write all extracted tables into a single SQLite database file.
    Creates tables, indices, and an audit manifest table.
    """
    if output_path.exists():
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(output_path))
    cursor = conn.cursor()

    # Enable WAL mode for high performance
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")

    # 1. Create audit manifest table
    cursor.execute(
        """
        CREATE TABLE _cloud_export_manifest (
            table_name TEXT PRIMARY KEY,
            project_id TEXT,
            dataset_id TEXT,
            row_count INTEGER,
            column_count INTEGER,
            source_bytes INTEGER,
            table_created TEXT,
            table_modified TEXT,
            export_timestamp_utc TEXT,
            export_timestamp_ist TEXT,
            columns_schema_json TEXT
        );
        """
    )

    total_rows = 0

    for tbl in extracted_tables:
        table_name = tbl["table_id"]
        cols = tbl["columns"]
        rows = tbl["rows"]
        total_rows += len(rows)

        # Build CREATE TABLE statement
        col_defs = []
        for c in cols:
            c_name = c["name"]
            c_type = map_bq_type_to_sqlite(c["type"])
            # In SQLite, bracket column names in case they collide with reserved keywords
            col_defs.append(f'"{c_name}" {c_type}')

        create_sql = f'CREATE TABLE "{table_name}" (\n    ' + ",\n    ".join(col_defs) + "\n);"
        cursor.execute(create_sql)

        # Insert rows using executemany
        if rows:
            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join([f'"{c["name"]}"' for c in cols])
            insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

            val_tuples = []
            for r in rows:
                val_tuples.append(tuple(sanitize_val_for_sqlite(r.get(c["name"])) for c in cols))

            cursor.executemany(insert_sql, val_tuples)

        # Helpful indices for high-frequency lookup fields
        col_name_set = {c["name"] for c in cols}
        for index_candidate in ("symbol", "cycle_id", "run_id", "source_timestamp", "prediction_date"):
            if index_candidate in col_name_set:
                idx_name = f"idx_{table_name}_{index_candidate}"
                cursor.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" ("{index_candidate}");')

        # Insert into manifest
        cursor.execute(
            """
            INSERT INTO _cloud_export_manifest (
                table_name, project_id, dataset_id, row_count, column_count,
                source_bytes, table_created, table_modified,
                export_timestamp_utc, export_timestamp_ist, columns_schema_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                table_name,
                project_id,
                dataset_id,
                len(rows),
                len(cols),
                tbl.get("num_bytes", 0),
                tbl.get("created"),
                tbl.get("modified"),
                now_utc.isoformat(),
                now_ist.isoformat(),
                json.dumps(cols),
            ),
        )

    conn.commit()
    conn.close()
    return total_rows


def write_to_json(
    extracted_tables: list[dict[str, Any]],
    output_path: Path,
    project_id: str,
    dataset_id: str,
    now_utc: datetime.datetime,
    now_ist: datetime.datetime,
) -> int:
    """
    Write all extracted tables into a single consolidated JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = sum(len(t["rows"]) for t in extracted_tables)

    bundle = {
        "export_metadata": {
            "project_id": project_id,
            "dataset_id": dataset_id,
            "export_timestamp_utc": now_utc.isoformat(),
            "export_timestamp_ist": now_ist.isoformat(),
            "total_tables": len(extracted_tables),
            "total_rows": total_rows,
        },
        "tables": {},
    }

    for tbl in extracted_tables:
        t_id = tbl["table_id"]
        sanitized_rows = []
        for r in tbl["rows"]:
            sanitized_rows.append({k: sanitize_val_for_json(v) for k, v in r.items()})

        bundle["tables"][t_id] = {
            "table_id": t_id,
            "num_rows": len(sanitized_rows),
            "num_bytes": tbl.get("num_bytes", 0),
            "created": tbl.get("created"),
            "modified": tbl.get("modified"),
            "columns": tbl["columns"],
            "rows": sanitized_rows,
        }

    output_path.write_text(json.dumps(bundle, indent=2, default=str), encoding="utf-8")
    return total_rows


def write_to_zip(
    extracted_tables: list[dict[str, Any]],
    output_path: Path,
    project_id: str,
    dataset_id: str,
    now_utc: datetime.datetime,
    now_ist: datetime.datetime,
) -> int:
    """
    Write all extracted tables as CSV files bundled inside a single ZIP archive.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_rows = 0

    manifest = {
        "project_id": project_id,
        "dataset_id": dataset_id,
        "export_timestamp_utc": now_utc.isoformat(),
        "export_timestamp_ist": now_ist.isoformat(),
        "tables": {},
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for tbl in extracted_tables:
            t_id = tbl["table_id"]
            cols = [c["name"] for c in tbl["columns"]]
            rows = tbl["rows"]
            total_rows += len(rows)

            manifest["tables"][t_id] = {
                "num_rows": len(rows),
                "num_columns": len(cols),
                "columns": tbl["columns"],
            }

            sio = io.StringIO()
            writer = csv.DictWriter(sio, fieldnames=cols, lineterminator="\n")
            writer.writeheader()
            for r in rows:
                clean_row = {k: sanitize_val_for_json(v) for k, v in r.items()}
                writer.writerow(clean_row)

            zf.writestr(f"{t_id}.csv", sio.getvalue())

        zf.writestr("_manifest.json", json.dumps(manifest, indent=2))

    return total_rows


def export_cloud_database(
    project_id: str | None = None,
    dataset_id: str | None = None,
    output_format: str = "sqlite",
    output_file: str | Path | None = None,
    output_dir: str | Path | None = None,
    include_backups: bool = True,
) -> dict[str, Any]:
    """
    Main programmatic entry point to extract everything from Google Cloud BigQuery
    into a single permanent file.
    """
    bq = get_bq_client(project_id)
    proj = project_id or getattr(bq, "project", DEFAULT_PROJECT_ID)
    dset = dataset_id or DEFAULT_DATASET_ID

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = now_utc.astimezone(ist_offset)
    timestamp_str = now_ist.strftime("%Y%m%d_%H%M%S")

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Discovering tables in Google Cloud BigQuery ({proj}.{dset})...")
    table_names = fetch_dataset_tables(bq, dset, include_backups=include_backups)
    print(f"      Found {len(table_names)} tables: {', '.join(table_names)}")

    print("[2/4] Extracting schemas, metadata, and all rows...")
    extracted_tables = []
    for idx, t_id in enumerate(table_names, 1):
        print(f"      ({idx}/{len(table_names)}) Extracting '{t_id}'...")
        t_data = extract_table_data(bq, proj, dset, t_id)
        print(f"         -> {len(t_data['rows'])} rows, {len(t_data['columns'])} columns")
        extracted_tables.append(t_data)

    print(f"[3/4] Generating permanent single-file export (format: {output_format})...")
    generated_files: list[Path] = []
    fmt = output_format.lower()

    if fmt in ("sqlite", "all") or (output_file and str(output_file).endswith(".db")):
        sqlite_path = Path(output_file) if (output_file and str(output_file).endswith(".db")) else (out_dir / f"{dset}_all_{timestamp_str}.db")
        # Also create/update a standard permanent symlink/copy path without timestamp
        permanent_sqlite_path = out_dir / f"{dset}_export_latest.db"
        write_to_sqlite(extracted_tables, sqlite_path, proj, dset, now_utc, now_ist)
        # Duplicate to latest
        import shutil
        shutil.copy2(sqlite_path, permanent_sqlite_path)
        generated_files.append(sqlite_path)
        generated_files.append(permanent_sqlite_path)

    if fmt in ("json", "all") or (output_file and str(output_file).endswith(".json")):
        json_path = Path(output_file) if (output_file and str(output_file).endswith(".json")) else (out_dir / f"{dset}_all_{timestamp_str}.json")
        permanent_json_path = out_dir / f"{dset}_export_latest.json"
        write_to_json(extracted_tables, json_path, proj, dset, now_utc, now_ist)
        import shutil
        shutil.copy2(json_path, permanent_json_path)
        generated_files.append(json_path)
        generated_files.append(permanent_json_path)

    if fmt in ("zip", "all") or (output_file and str(output_file).endswith(".zip")):
        zip_path = Path(output_file) if (output_file and str(output_file).endswith(".zip")) else (out_dir / f"{dset}_all_{timestamp_str}.zip")
        permanent_zip_path = out_dir / f"{dset}_export_latest.zip"
        write_to_zip(extracted_tables, zip_path, proj, dset, now_utc, now_ist)
        import shutil
        shutil.copy2(zip_path, permanent_zip_path)
        generated_files.append(zip_path)
        generated_files.append(permanent_zip_path)

    total_rows = sum(len(t["rows"]) for t in extracted_tables)
    print(f"[4/4] Export completed successfully!")
    print(f"      Total tables extracted: {len(extracted_tables)}")
    print(f"      Total records extracted: {total_rows}")
    print("      Generated files:")
    for gf in generated_files:
        size_kb = gf.stat().st_size / 1024
        print(f"        - {gf} ({size_kb:.1f} KB)")

    return {
        "project_id": proj,
        "dataset_id": dset,
        "tables_count": len(extracted_tables),
        "total_rows": total_rows,
        "generated_files": [str(p) for p in generated_files],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract all datasets, tables, schemas, and rows from Google Cloud BigQuery into a single permanent file."
    )
    parser.add_argument("--project", help=f"Google Cloud Project ID (default: {DEFAULT_PROJECT_ID})")
    parser.add_argument("--dataset", default=DEFAULT_DATASET_ID, help=f"BigQuery Dataset ID (default: {DEFAULT_DATASET_ID})")
    parser.add_argument(
        "--format",
        choices=["sqlite", "json", "zip", "all"],
        default="all",
        help="Export single-file format (default: 'all' generates SQLite .db and JSON bundle)",
    )
    parser.add_argument("--output-file", help="Custom path for single output file")
    parser.add_argument("--output-dir", help=f"Target output directory (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument(
        "--active-only",
        action="store_true",
        help="Export only active tables, skipping backup tables",
    )

    args = parser.parse_args()

    export_cloud_database(
        project_id=args.project,
        dataset_id=args.dataset,
        output_format=args.format,
        output_file=args.output_file,
        output_dir=args.output_dir,
        include_backups=not args.active_only,
    )


if __name__ == "__main__":
    main()
