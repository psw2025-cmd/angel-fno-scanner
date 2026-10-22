"""Regression: a truthy string is not independent actual verification."""
import pytest
from src.phase5_engine.validation import evaluate_gap_up

P = {
    "prediction_id": "verified-boolean-gate",
    "track": "gap_up",
    "published_at": "2026-10-15T10:00:00+05:30",
    "target_date": "2026-10-16",
    "symbol": "TEST",
    "previous_close": 100,
    "predicted_gap_pct": 1,
}

@pytest.mark.parametrize("flag", ["true", "false", 1, None, [], {}])
def test_unverified_truthy_values_never_score(monkeypatch, flag):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")
    result = evaluate_gap_up([P], {"TEST": {
        "verified_open": flag, "session_date": "2026-10-16", "open_price": 102
    }})
    assert result["evaluated"] == 0
    assert result["pending"] == 1
    assert result["accuracy_pct"] is None
    assert result["rows"][0]["status"] == "PENDING_ACTUAL"

def test_explicit_true_scores(monkeypatch):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")
    result = evaluate_gap_up([P], {"TEST": {
        "verified_open": True, "session_date": "2026-10-16", "open_price": 102
    }})
    assert result["evaluated"] == 1
    assert result["accuracy_pct"] == 100.0
