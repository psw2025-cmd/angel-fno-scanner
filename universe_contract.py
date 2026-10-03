"""Reviewed manifest identity is the publication contract, not a minimum count."""
import json
from pathlib import Path

EXPECTED_FNO_UNIVERSE_COUNT = 219


def verified_symbols(manifest_path=None):
    path = Path(manifest_path) if manifest_path else Path(__file__).with_name("agent_manifest.json")
    universe = json.loads(path.read_text(encoding="utf-8"))["universe"]
    symbols = universe["symbols"]
    if (universe["total_symbols"] != EXPECTED_FNO_UNIVERSE_COUNT
            or len(symbols) != EXPECTED_FNO_UNIVERSE_COUNT
            or len(set(symbols)) != EXPECTED_FNO_UNIVERSE_COUNT
            or any(not isinstance(s, str) or not s or s != s.strip().upper() for s in symbols)):
        raise RuntimeError("Verified F&O manifest must contain exactly 219 unique normalized symbols")
    return tuple(symbols)


def select_verified_universe(discovered):
    """Ignore new unreviewed listings; fail closed on any missing reviewed identity."""
    symbols = verified_symbols()
    missing = sorted(set(symbols) - set(discovered))
    if missing:
        raise RuntimeError("F&O universe incomplete: missing verified symbols: " + ", ".join(missing))
    return {symbol: discovered[symbol] for symbol in symbols}


def require_verified_symbols(symbols):
    symbols = list(symbols)
    expected = set(verified_symbols())
    actual = set(symbols)
    if len(symbols) != 219 or len(actual) != 219 or actual != expected:
        raise RuntimeError("F&O publication incomplete or invalid: missing="
                           + ",".join(sorted(expected - actual))
                           + "; unexpected=" + ",".join(sorted(actual - expected)))
