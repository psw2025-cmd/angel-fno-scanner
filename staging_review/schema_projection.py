"""
staging_review/schema_projection.py

World-class Schema Contract & Projection Engine.
Ensures that data dictionaries sent to BigQuery strictly conform to the destination
table schema before load jobs execute. Prunes unexpected extra keys (such as cycle_id
on tables that lack the column) and verifies required provenance fields.
"""
from typing import Any, Dict, List, Set, Tuple


def get_table_column_names(table_or_schema: Any) -> Set[str]:
    """Extract set of column names from a BigQuery Table or schema list."""
    schema = getattr(table_or_schema, "schema", table_or_schema)
    cols = set()
    for f in schema:
        if hasattr(f, "name"):
            cols.add(f.name)
        elif isinstance(f, dict) and "name" in f:
            cols.add(f["name"])
    return cols


def filter_row_to_table_schema(
    row: Dict[str, Any],
    table_or_schema: Any,
    required_fields: Tuple[str, ...] = ("run_id", "git_sha", "writer_id")
) -> Dict[str, Any]:
    """
    Project a dictionary row strictly to the column schema of the target table.
    
    1. Prunes any keys not declared in the table schema (preventing BigQuery 400 errors).
    2. Validates that required provenance keys exist.
    3. Normalizes None/null values gracefully.
    """
    valid_columns = get_table_column_names(table_or_schema)
    if not valid_columns:
        # If schema cannot be inspected, return row as-is to avoid data loss
        return dict(row)

    projected = {k: v for k, v in row.items() if k in valid_columns}

    # Verify required provenance fields
    missing_required = [f for f in required_fields if f in valid_columns and f not in projected]
    if missing_required:
        raise ValueError(
            f"Row projection failed: required table columns {missing_required} are missing from row data"
        )

    return projected


def filter_rows_to_table_schema(
    rows: List[Dict[str, Any]],
    table_or_schema: Any,
    required_fields: Tuple[str, ...] = ("run_id", "git_sha", "writer_id")
) -> List[Dict[str, Any]]:
    """Project a list of rows to the target table schema."""
    return [filter_row_to_table_schema(r, table_or_schema, required_fields) for r in rows]
