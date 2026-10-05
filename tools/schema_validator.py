"""
tools/schema_validator.py

Fail-fast schema validation engine for Angel F&O Scanner BigQuery tables.
Enforces that every record matches declarative schema definitions in schemas/*.json:
- Strictly rejects undeclared/unknown columns (zero silent column projection).
- Enforces REQUIRED field presence and non-nullability.
- Performs strict in-memory type validation matching BigQuery data types.
"""

from __future__ import annotations

import datetime
import json
import math
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

_SCHEMA_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


class SchemaValidationError(Exception):
    """Raised when one or more rows violate the declarative BigQuery schema contract."""

    def __init__(
        self,
        message: str,
        table_name: str,
        row_index: int | None = None,
        errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.table_name = table_name
        self.row_index = row_index
        self.errors = errors if errors is not None else [message]

    def __str__(self) -> str:
        idx_str = f" at row {self.row_index}" if self.row_index is not None else ""
        if len(self.errors) > 1:
            details = "\n  - " + "\n  - ".join(self.errors)
            return f"Schema validation failed for table '{self.table_name}'{idx_str}:{details}"
        return f"Schema validation failed for table '{self.table_name}'{idx_str}: {self.errors[0]}"


def load_schema(table_name: str) -> list[dict[str, Any]]:
    """
    Load the declarative schema definition for table_name from schemas/{table_name}.json.
    Returns a list of field dictionaries: [{"name": ..., "type": ..., "mode": ...}, ...]
    """
    schema_path = SCHEMAS_DIR / f"{table_name}.json"
    if not schema_path.exists():
        raise FileNotFoundError(
            f"Declarative schema definition not found for table '{table_name}': {schema_path}"
        )
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(
            f"Schema file '{schema_path.name}' must contain a top-level list of field definitions"
        )
    return data


def get_schema_field_map(table_name: str) -> dict[str, dict[str, Any]]:
    """
    Return a cached dictionary mapping column_name -> field definition dictionary.
    """
    if table_name not in _SCHEMA_CACHE:
        fields = load_schema(table_name)
        field_map = {f["name"]: f for f in fields}
        _SCHEMA_CACHE[table_name] = field_map
    return _SCHEMA_CACHE[table_name]


def _check_type(val: Any, expected_type: str, col_name: str) -> str | None:
    """
    Check val against expected BigQuery type. Returns an error message string if invalid, else None.
    """
    exp = expected_type.upper()

    if exp == "STRING":
        if not isinstance(val, str):
            return f"Field '{col_name}' expects STRING, got {type(val).__name__} ({repr(val)})"
        return None

    if exp in ("INT64", "INTEGER"):
        # In Python, bool is a subclass of int. Reject bool explicitly.
        if isinstance(val, bool) or not isinstance(val, int):
            return f"Field '{col_name}' expects INT64, got {type(val).__name__} ({repr(val)})"
        return None

    if exp in ("FLOAT64", "FLOAT"):
        # Accept int or float, but reject bool and non-finite floats
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"Field '{col_name}' expects FLOAT64, got {type(val).__name__} ({repr(val)})"
        if math.isnan(val) or math.isinf(val):
            return f"Field '{col_name}' expects finite FLOAT64, got {val}"
        return None

    if exp in ("BOOL", "BOOLEAN"):
        if not isinstance(val, bool):
            return f"Field '{col_name}' expects BOOL, got {type(val).__name__} ({repr(val)})"
        return None

    if exp == "TIMESTAMP":
        if isinstance(val, datetime.datetime):
            return None
        if isinstance(val, str):
            # Parse ISO or standard timestamp string
            cleaned = val.strip().replace("Z", "+00:00")
            # Try fromisoformat or standard space separator
            try:
                datetime.datetime.fromisoformat(cleaned)
                return None
            except ValueError:
                # Also try standard format "%Y-%m-%d %H:%M:%S"
                try:
                    datetime.datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
                    return None
                except ValueError:
                    return f"Field '{col_name}' expects TIMESTAMP (datetime or valid ISO string), got invalid timestamp string: {repr(val)}"
        return f"Field '{col_name}' expects TIMESTAMP (datetime or ISO string), got {type(val).__name__}"

    if exp == "DATE":
        # In Python, datetime is a subclass of date. Reject datetime objects for DATE fields!
        if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
            return None
        if isinstance(val, str):
            cleaned = val.strip()
            # Must strictly match YYYY-MM-DD
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned):
                try:
                    datetime.date.fromisoformat(cleaned)
                    return None
                except ValueError:
                    return f"Field '{col_name}' expects DATE string in YYYY-MM-DD format with valid calendar date, got {repr(val)}"
            return f"Field '{col_name}' expects DATE (date or 'YYYY-MM-DD' string), got {repr(val)}"
        return f"Field '{col_name}' expects DATE (date or 'YYYY-MM-DD' string), got {type(val).__name__}"

    # Unknown BigQuery type
    return None


def validate_row(table_name: str, row: dict[str, Any], row_index: int = 0) -> None:
    """
    Validate a single row dictionary against the declarative schema of table_name.
    Raises SchemaValidationError on the first set of errors detected.
    """
    field_map = get_schema_field_map(table_name)
    errors: list[str] = []

    # 1. Check for undeclared / extraneous columns (Fail-Fast: no silent dropping)
    for col in row:
        if col not in field_map:
            errors.append(f"Undeclared column '{col}' is not present in schema for table '{table_name}'")

    # 2. Check each schema column for presence, nullability, and types
    for col_name, field_def in field_map.items():
        mode = field_def.get("mode", "NULLABLE").upper()
        expected_type = field_def.get("type", "STRING")

        if col_name not in row:
            if mode == "REQUIRED":
                errors.append(f"Missing REQUIRED column '{col_name}'")
            continue

        val = row[col_name]
        if val is None:
            if mode == "REQUIRED":
                errors.append(f"Column '{col_name}' is REQUIRED but value is None")
            continue

        # Non-null value: validate type
        type_err = _check_type(val, expected_type, col_name)
        if type_err:
            errors.append(type_err)

    if errors:
        msg = f"Row {row_index} failed schema validation for table '{table_name}': {'; '.join(errors)}"
        raise SchemaValidationError(
            message=msg,
            table_name=table_name,
            row_index=row_index,
            errors=errors,
        )


def validate_rows(table_name: str, rows: list[dict[str, Any]]) -> None:
    """
    Validate a list of row dictionaries against the declarative schema of table_name.
    Raises SchemaValidationError on the first row that violates the schema.
    """
    if not isinstance(rows, list):
        raise TypeError(f"rows must be a list of dictionaries, got {type(rows).__name__}")

    # Ensure schema loads even if batch is empty
    get_schema_field_map(table_name)

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SchemaValidationError(
                message=f"Row {idx} is not a dictionary: {type(row).__name__}",
                table_name=table_name,
                row_index=idx,
                errors=[f"Expected dictionary at index {idx}, got {type(row).__name__}"],
            )
        validate_row(table_name, row, row_index=idx)
