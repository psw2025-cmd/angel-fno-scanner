"""
tests/test_export_cloud_database.py

Unit tests for tools/export_cloud_database.py.
Verifies type mapping, value sanitization, and single-file export generation (SQLite, JSON, ZIP).
"""

from __future__ import annotations

import datetime
import json
import sqlite3
import zipfile
from pathlib import Path
import pytest

from tools.export_cloud_database import (
    map_bq_type_to_sqlite,
    sanitize_val_for_sqlite,
    sanitize_val_for_json,
    write_to_sqlite,
    write_to_json,
    write_to_zip,
)


def test_map_bq_type_to_sqlite():
    assert map_bq_type_to_sqlite("INT64") == "INTEGER"
    assert map_bq_type_to_sqlite("INTEGER") == "INTEGER"
    assert map_bq_type_to_sqlite("FLOAT64") == "REAL"
    assert map_bq_type_to_sqlite("NUMERIC") == "REAL"
    assert map_bq_type_to_sqlite("BOOL") == "INTEGER"
    assert map_bq_type_to_sqlite("BOOLEAN") == "INTEGER"
    assert map_bq_type_to_sqlite("STRING") == "TEXT"
    assert map_bq_type_to_sqlite("TIMESTAMP") == "TEXT"
    assert map_bq_type_to_sqlite("DATE") == "TEXT"
    assert map_bq_type_to_sqlite("BYTES") == "BLOB"


def test_sanitize_val_for_sqlite():
    assert sanitize_val_for_sqlite(None) is None
    assert sanitize_val_for_sqlite(True) == 1
    assert sanitize_val_for_sqlite(False) == 0
    assert sanitize_val_for_sqlite(datetime.date(2026, 10, 5)) == "2026-10-05"
    dt = datetime.datetime(2026, 10, 5, 9, 15, 0)
    assert sanitize_val_for_sqlite(dt) == "2026-10-05T09:15:00"
    assert sanitize_val_for_sqlite({"a": 1}) == '{"a": 1}'
    assert sanitize_val_for_sqlite(b"bytes") == b"bytes"


def test_sanitize_val_for_json():
    assert sanitize_val_for_json(None) is None
    assert sanitize_val_for_json(datetime.date(2026, 10, 5)) == "2026-10-05"
    assert sanitize_val_for_json(b"hello") == "hello"


def test_export_writers_roundtrip(tmp_path: Path):
    sample_table = {
        "table_id": "test_predictions",
        "num_rows": 2,
        "num_bytes": 1024,
        "created": "2026-10-05T09:00:00Z",
        "modified": "2026-10-05T09:15:00Z",
        "columns": [
            {"name": "symbol", "type": "STRING", "mode": "REQUIRED", "description": "Symbol"},
            {"name": "spot_ltp", "type": "FLOAT64", "mode": "NULLABLE", "description": "LTP"},
            {"name": "is_active", "type": "BOOL", "mode": "NULLABLE", "description": "Active flag"},
            {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE", "description": "Timestamp"},
        ],
        "rows": [
            {"symbol": "NIFTY", "spot_ltp": 25000.5, "is_active": True, "created_at": "2026-10-05T09:15:00Z"},
            {"symbol": "BANKNIFTY", "spot_ltp": 52000.0, "is_active": False, "created_at": "2026-10-05T09:15:00Z"},
        ],
    }

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_ist = now_utc + datetime.timedelta(hours=5, minutes=30)

    # 1. SQLite test
    db_path = tmp_path / "test.db"
    total_rows = write_to_sqlite([sample_table], db_path, "test_proj", "test_dset", now_utc, now_ist)
    assert total_rows == 2
    assert db_path.exists()

    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    rows = c.execute("SELECT symbol, spot_ltp, is_active FROM test_predictions ORDER BY symbol").fetchall()
    assert len(rows) == 2
    assert rows[0] == ("BANKNIFTY", 52000.0, 0)
    assert rows[1] == ("NIFTY", 25000.5, 1)

    manifest_rows = c.execute("SELECT table_name, row_count, column_count FROM _cloud_export_manifest").fetchall()
    assert len(manifest_rows) == 1
    assert manifest_rows[0] == ("test_predictions", 2, 4)
    conn.close()

    # 2. JSON test
    json_path = tmp_path / "test.json"
    total_json_rows = write_to_json([sample_table], json_path, "test_proj", "test_dset", now_utc, now_ist)
    assert total_json_rows == 2
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["export_metadata"]["total_rows"] == 2
    assert "test_predictions" in data["tables"]
    assert len(data["tables"]["test_predictions"]["rows"]) == 2

    # 3. ZIP test
    zip_path = tmp_path / "test.zip"
    total_zip_rows = write_to_zip([sample_table], zip_path, "test_proj", "test_dset", now_utc, now_ist)
    assert total_zip_rows == 2
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "test_predictions.csv" in namelist
        assert "_manifest.json" in namelist
