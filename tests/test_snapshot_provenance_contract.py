"""Regression: snapshot generation must never silently fall back to writer clock."""
from pathlib import Path


def test_verified_cycle_timestamp_is_used_for_export():
    source = (Path(__file__).resolve().parents[1] / 'agent_cli.py').read_text(encoding='utf-8')
    assert 'verified_source_timestamp=str(meta["source_timestamp"])' in source
    assert 'meta.get("data_freshness_status") != "EXCHANGE_VERIFIED"' in source
    assert 'feed_candidates = [verified_source_timestamp]' in source
    assert 'feed_candidates = [health.get("timestamp_utc")]' not in source


def test_missing_provenance_fails_closed():
    source = (Path(__file__).resolve().parents[1] / 'agent_cli.py').read_text(encoding='utf-8')
    assert 'Missing exchange timestamp and verified cycle provenance; fail-closed' in source
