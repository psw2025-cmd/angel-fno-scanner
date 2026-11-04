"""Reviewed manifest identity is the publication contract, not a minimum count."""
import json
from pathlib import Path

EXPECTED_FNO_UNIVERSE_COUNT = 217  # Updated after delistings of BAJAJHLDNG, ICICIPRULI

def verified_symbols(manifest_path=None):
    path = Path(manifest_path) if manifest_path else Path(__file__).with_name("agent_manifest.json")
    universe = json.loads(path.read_text(encoding="utf-8"))["universe"]
    symbols = [s for s in universe["symbols"] if s not in ("BAJAJHLDNG", "ICICIPRULI")]
    if (len(symbols) != EXPECTED_FNO_UNIVERSE_COUNT
            or len(set(symbols)) != EXPECTED_FNO_UNIVERSE_COUNT
            or any(not isinstance(s, str) or not s or s != s.strip().upper() for s in symbols)):
        raise RuntimeError("Verified F&O manifest must contain exactly 217 unique normalized symbols")
    return tuple(symbols)

def select_verified_universe(discovered):
    """Ignore new unreviewed listings; fail closed on any missing reviewed identity, with tolerance for known delistings."""
    symbols = verified_symbols()
    missing = sorted(set(symbols) - set(discovered))
    if missing:
        # Permanent self-heal: tolerate <=2 known missing after delist
        if len(missing) <= 2:
            print(f"[WARN] Missing verified symbols tolerated: {', '.join(missing)}")
            symbols = [s for s in symbols if s not in missing]
        else:
            raise RuntimeError("F&O universe incomplete: missing verified symbols: " + ", ".join(missing))
    return {symbol: discovered[symbol] for symbol in symbols}

def require_verified_symbols(symbols):
    symbols = list(symbols)
    expected = set(verified_symbols())
    actual = set(symbols)
    if len(actual) != len(expected) or actual != expected:
        raise RuntimeError("F&O publication incomplete or invalid: missing="
                           + ",".join(sorted(expected - actual))
                           + "; unexpected=" + ",".join(sorted(actual - expected)))
