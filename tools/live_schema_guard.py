"""Refuse a WRITE_TRUNCATE that would narrow option_predictions_live.

The committed schema is the contract. A live table that is missing provenance
fields, or a load schema narrower than the live table, must not replace the
production table. Autodetect loads are refused. This module does not alter
BigQuery.
"""
from __future__ import annotations

REQUIRED_PROVENANCE = (
    ("run_id", "STRING"),
    ("git_sha", "STRING"),
    ("writer_id", "STRING"),
    ("source_timestamp", "TIMESTAMP"),
    ("cycle_id", "STRING"),
)


class SchemaGuardError(RuntimeError):
    """Raised when a truncate load would drop or mistype production fields."""


def _name(field) -> str:
    if isinstance(field, dict):
        return str(field.get("name") or "")
    return str(getattr(field, "name", "") or "")


def _type(field) -> str:
    if isinstance(field, dict):
        raw = field.get("type") or field.get("field_type") or ""
    else:
        raw = getattr(field, "field_type", None) or getattr(field, "type", "")
    return str(raw).upper()


def field_map(fields) -> dict[str, str]:
    mapped = {}
    for field in fields or []:
        name = _name(field)
        if not name:
            raise SchemaGuardError("schema field is missing a name")
        if name in mapped:
            raise SchemaGuardError(f"duplicate schema field {name}")
        mapped[name] = _type(field)
    return mapped


def require_committed_provenance(committed_fields) -> dict[str, str]:
    """Fail closed when the committed contract lacks provenance or mistypes run_id."""
    committed = field_map(committed_fields)
    missing = []
    wrong = []
    for name, expected in REQUIRED_PROVENANCE:
        actual = committed.get(name)
        if actual is None:
            missing.append(name)
        elif actual != expected:
            wrong.append(f"{name}={actual} expected {expected}")
    if missing or wrong:
        raise SchemaGuardError(
            "committed option_predictions_live schema is not loadable: "
            f"missing={missing or 'none'} wrong={wrong or 'none'}"
        )
    return committed


def assert_truncate_schema_safe(committed_fields, live_fields, load_fields=None, *, autodetect: bool = False) -> None:
    """Refuse WRITE_TRUNCATE unless the load keeps every live column and provenance type.

    A live table that is missing a required provenance field is refused. Add the
    column first. Do not truncate the rows to repair the schema.
    """
    if autodetect:
        raise SchemaGuardError(
            "autodetect WRITE_TRUNCATE is refused for option_predictions_live"
        )
    committed = require_committed_provenance(committed_fields)
    live = field_map(live_fields)
    load = field_map(committed_fields if load_fields is None else load_fields)

    for name, expected in REQUIRED_PROVENANCE:
        if load.get(name) != expected:
            raise SchemaGuardError(
                f"load schema provenance {name}={load.get(name)} expected {expected}"
            )
        if name not in live:
            raise SchemaGuardError(
                f"live option_predictions_live is missing {name}; "
                "refusing WRITE_TRUNCATE until the column is added"
            )
        if live[name] != expected:
            raise SchemaGuardError(
                f"live option_predictions_live {name}={live[name]} expected {expected}; "
                "refusing to retype it with WRITE_TRUNCATE"
            )

    dropped = sorted(set(live) - set(load))
    if dropped:
        raise SchemaGuardError(
            "load schema is narrower than the live table and would drop: " + ", ".join(dropped)
        )
    def _canon(t: str) -> str:
        t = (t or "").upper()
        if t in ("FLOAT", "FLOAT64"):
            return "FLOAT64"
        if t in ("INTEGER", "INT64"):
            return "INT64"
        return t
    retyped = sorted(
        name for name, live_type in live.items()
        if name in load and _canon(load[name]) != _canon(live_type)
    )
    if retyped:
        detail = ", ".join(f"{name} live={live[name]} load={load[name]}" for name in retyped)
        raise SchemaGuardError("load schema would retype live columns: " + detail)
    # The load must also carry every committed field so an older container cannot
    # publish a schema that omits columns the contract requires but the live table
    # has not received yet. The missing-live check above already stops that case.
    missing_from_load = sorted(set(committed) - set(load))
    if missing_from_load:
        raise SchemaGuardError(
            "load schema omits committed fields: " + ", ".join(missing_from_load)
        )

