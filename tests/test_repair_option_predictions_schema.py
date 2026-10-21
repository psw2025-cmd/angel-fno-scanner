"""The live time column is repaired only when it is empty and the wrong type."""
import pytest

from tools.repair_option_predictions_schema import SchemaRepairError, plan_repairs


def test_empty_string_timestamp_plans_a_retype_and_two_columns():
    steps = plan_repairs({"source_timestamp": "STRING", "run_id": "STRING"}, 0)
    assert steps == [
        ("drop_column", "source_timestamp", ""),
        ("add_column", "source_timestamp", "TIMESTAMP"),
        ("add_column", "cycle_id", "STRING"),
        ("add_column", "data_freshness_status", "STRING"),
    ]


def test_values_in_the_string_column_fail_closed():
    with pytest.raises(SchemaRepairError, match="holds values"):
        plan_repairs({"source_timestamp": "STRING"}, 3)


def test_already_aligned_table_needs_no_change():
    assert plan_repairs(
        {
            "source_timestamp": "TIMESTAMP",
            "cycle_id": "STRING",
            "data_freshness_status": "STRING",
        },
        0,
    ) == []


def test_wrong_cycle_id_type_fails_closed():
    with pytest.raises(SchemaRepairError, match="cycle_id"):
        plan_repairs(
            {
                "source_timestamp": "TIMESTAMP",
                "cycle_id": "INTEGER",
                "data_freshness_status": "STRING",
            },
            0,
        )
