"""Invalid metric domains must never enter challenger selection."""
import pytest
from src.phase5_engine.learning import choose

BASE = dict(sample_count=120, precision=.6, brier_score=.2, max_drawdown=.1,
            walk_forward=True, data_leakage_detected=False)
TRIAL = dict(sample_count=120, precision=.7, brier_score=.1, max_drawdown=.08,
             walk_forward=True, data_leakage_detected=False)

@pytest.mark.parametrize("field,value", [
    ("sample_count", -1), ("sample_count", 100.5),
    ("precision", -0.1), ("precision", 1.01),
    ("brier_score", -0.1), ("brier_score", 1.01),
    ("max_drawdown", -0.1), ("max_drawdown", 1.01),
])
@pytest.mark.parametrize("side", ["baseline", "trial"])
def test_out_of_domain_metric_rejected(monkeypatch, field, value, side):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")
    baseline, trial = BASE.copy(), TRIAL.copy()
    (baseline if side == "baseline" else trial)[field] = value
    with pytest.raises(ValueError, match="outside valid domains"):
        choose("gap_up", {"old": 1}, {"new": 1}, baseline, trial)

def test_valid_metrics_promote(monkeypatch):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")
    result = choose("gap_up", {"old": 1}, {"new": 1}, BASE, TRIAL)
    assert result["decision"] == "PROMOTE_CANDIDATE"
