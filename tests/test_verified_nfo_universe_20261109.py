import json
from pathlib import Path

from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT, verified_symbols


def test_manifest_reconciles_renamed_and_delisted_nfo_symbols():
    symbols = verified_symbols()
    assert len(symbols) == EXPECTED_FNO_UNIVERSE_COUNT == 219
    assert len(set(symbols)) == 219
    assert "ICICILIFE" in symbols
    assert "COROMANDEL" in symbols
    assert "ICICIPRULI" not in symbols
    assert "BAJAJHLDNG" not in symbols


def test_manifest_universe_identity_matches_contract():
    data = json.loads(Path(__file__).resolve().parents[1].joinpath("agent_manifest.json").read_text(encoding="utf-8"))
    assert set(data["universe"]["symbols"]) == set(verified_symbols())
