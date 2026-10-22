import pytest

from tools.live_schema_guard import SchemaGuardError, assert_truncate_schema_safe, canonical_type


@pytest.mark.parametrize(("raw", "expected"), [
    ("FLOAT", "FLOAT64"), ("FLOAT64", "FLOAT64"),
    ("INTEGER", "INT64"), ("INT64", "INT64"),
    ("BOOLEAN", "BOOL"), ("BOOL", "BOOL"),
])
def test_bigquery_aliases(raw, expected):
    assert canonical_type(raw) == expected


def test_truncate_accepts_only_equivalent_aliases():
    committed = [
        {"name": "run_id", "type": "STRING"},
        {"name": "git_sha", "type": "STRING"},
        {"name": "writer_id", "type": "STRING"},
        {"name": "source_timestamp", "type": "TIMESTAMP"},
        {"name": "cycle_id", "type": "STRING"},
        {"name": "price", "type": "FLOAT"},
        {"name": "quantity", "type": "INTEGER"},
        {"name": "is_active", "type": "BOOLEAN"},
    ]
    live = [dict(f) for f in committed]
    for f in live:
        f["type"] = {"FLOAT": "FLOAT64", "INTEGER": "INT64", "BOOLEAN": "BOOL"}.get(f["type"], f["type"])
    assert_truncate_schema_safe(committed, live, load_fields=committed)


def test_truncate_still_refuses_real_retyping():
    committed = [
        {"name": n, "type": t}
        for n, t in (
            ("run_id", "STRING"), ("git_sha", "STRING"), ("writer_id", "STRING"),
            ("source_timestamp", "TIMESTAMP"), ("cycle_id", "STRING"),
            ("price", "FLOAT64"),
        )
    ]
    live = [dict(f) for f in committed]
    live[-1]["type"] = "STRING"
    with pytest.raises(SchemaGuardError, match="retype"):
        assert_truncate_schema_safe(committed, live)
