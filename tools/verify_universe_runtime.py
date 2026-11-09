"""Read-only Cloud Run runtime verification of the frozen 219-symbol contract."""
import json
import os
from pathlib import Path

from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT, verified_symbols


def main() -> None:
    assert os.getenv("PAPER_MODE") == "1", "PAPER_MODE must be 1"
    assert os.getenv("LIVE_ORDER_AUTHORITY", "0") == "0"
    assert os.getenv("REAL_BROKER_ORDERS", "0") == "0"
    assert os.getenv("ALLOW_PRODUCTION_WRITES", "0") == "0"
    symbols = verified_symbols()
    manifest = json.loads(Path(__file__).resolve().parents[1].joinpath("agent_manifest.json").read_text(encoding="utf-8"))
    assert len(symbols) == EXPECTED_FNO_UNIVERSE_COUNT == 219
    assert len(set(symbols)) == 219
    assert set(symbols) == set(manifest["universe"]["symbols"])
    assert "ICICILIFE" in symbols and "COROMANDEL" in symbols
    assert "ICICIPRULI" not in symbols and "BAJAJHLDNG" not in symbols
    print("PASS: CLOUD_UNIVERSE_219", len(symbols), "PAPER_ONLY")


if __name__ == "__main__":
    main()
