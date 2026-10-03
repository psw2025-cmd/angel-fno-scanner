import pytest

import agent_cli


@pytest.mark.parametrize("query", [agent_cli.query_predictions, agent_cli.query_news])
def test_sql_symbol_injection_rejected_before_cloud_access(query, monkeypatch):
    monkeypatch.setattr(agent_cli, "get_bq", lambda: pytest.fail("cloud access"))
    with pytest.raises(ValueError, match="Invalid symbol"):
        query("SAIL'; SELECT 1; --")


@pytest.mark.parametrize("query", [agent_cli.query_predictions, agent_cli.query_news,
                                   agent_cli.query_top_gapup, agent_cli.query_top_breakouts])
def test_sql_limit_injection_rejected_before_cloud_access(query, monkeypatch):
    monkeypatch.setattr(agent_cli, "get_bq", lambda: pytest.fail("cloud access"))
    with pytest.raises(ValueError, match="Limit"):
        query(limit="1; SELECT 1")


def test_valid_query_inputs_support_exchange_symbols_and_internal_export_limit():
    assert agent_cli.validate_query_inputs("m&m", "250") == ("M&M", 250)
