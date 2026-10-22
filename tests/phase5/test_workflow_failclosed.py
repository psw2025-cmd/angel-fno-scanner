"""Scheduled Phase5 scaffolds must never report production success."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize("name", ["phase5_eod.yml", "phase5_validation.yml", "phase5_learning.yml"])
def test_scaffold_fails_closed(name):
    source = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
    assert "PHASE5_SCAFFOLD_ONLY:" in source
    assert "exit 1" in source.split("PHASE5_SCAFFOLD_ONLY:", 1)[1]
    assert "PAPER_MODE: '1'" in source
    assert "LIVE_ORDER_AUTHORITY: '0'" in source
