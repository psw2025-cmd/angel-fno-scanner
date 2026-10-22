"""Reject ambiguous learning verification flags before selecting model weights."""
import pytest
from src.phase5_engine.learning import choose

BASE = dict(sample_count=120, precision=.6, brier_score=.2, max_drawdown=.1,
            walk_forward=True, data_leakage_detected=False)
TRIAL = dict(sample_count=120, precision=.7, brier_score=.1, max_drawdown=.08,
             walk_forward=True, data_leakage_detected=False)

@pytest.mark.parametrize("side", ["baseline", "trial"])
@pytest.mark.parametrize("field", ["walk_forward", "data_leakage_detected"])
@pytest.mark.parametrize("invalid", ["false", "true", 0, 1, None])
def test_non_boolean_verification_rejected(monkeypatch, side, field, invalid):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")
    baseline, trial = BASE.copy(), TRIAL.copy()
    (baseline if side == "baseline" else trial)[field] = invalid
    with pytest.raises(ValueError, match="must be boolean"):
        choose("gap_up", {"old": 1}, {"new": 1}, baseline, trial)
