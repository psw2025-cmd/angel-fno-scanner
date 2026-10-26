"""Offline regression for expiry pairing; no broker, network, or cloud writes."""
import ast
from pathlib import Path
from tools.universe_pairing import nearest_complete_expiry, discovery_gap_reasons

def _pair(ce=True, pe=True):
    return {k: {"symbol": k} for k, enabled in (("CE", ce), ("PE", pe)) if enabled}

def test_first_complete_expiry_selected():
    assert nearest_complete_expiry({1: {100: _pair()}, 2: {110: _pair()}})[0] == 1

def test_later_complete_expiry_selected_when_front_month_one_sided():
    expiry, strikes = nearest_complete_expiry({1: {100: _pair(pe=False)}, 2: {110: _pair()}})
    assert (expiry, list(strikes)) == (2, [110])

def test_no_cross_strike_side_join():
    assert nearest_complete_expiry({1: {100: _pair(pe=False), 110: _pair(ce=False)}}) == (None, {})

def test_no_cross_expiry_side_join():
    assert nearest_complete_expiry({1: {100: _pair(pe=False)}, 2: {100: _pair(ce=False)}}) == (None, {})

def test_empty_expiry_map_fails_closed():
    assert nearest_complete_expiry({}) == (None, {})

def test_all_incomplete_expiries_fail_closed():
    assert nearest_complete_expiry({1: {100: _pair(pe=False)}, 2: {110: _pair(ce=False)}}) == (None, {})

def test_empty_side_dict_does_not_qualify():
    assert nearest_complete_expiry({1: {100: {}}}) == (None, {})

def test_unsorted_insertion_chooses_earliest_valid_expiry():
    assert nearest_complete_expiry({3: {120: _pair()}, 1: {100: _pair()}, 2: {110: _pair()}})[0] == 1

def test_only_complete_strikes_returned():
    _, strikes = nearest_complete_expiry({1: {100: _pair(), 110: _pair(pe=False)}})
    assert list(strikes) == [100]

def test_both_absent_reason():
    assert discovery_gap_reasons(["X"], {}, {}, {}) == {"X": "NO_VALID_OPTIONS_OR_FUTURES"}

def test_missing_futures_reason():
    assert discovery_gap_reasons(["X"], {"X": {1: {100: _pair()}}}, {}, {}) == {"X": "NO_VALID_FUTURES"}

def test_missing_options_reason():
    assert discovery_gap_reasons(["X"], {}, {"X": [{"token": "not-logged"}]}, {}) == {"X": "NO_VALID_OPTIONS"}

def test_no_paired_strike_reason():
    assert discovery_gap_reasons(["X"], {"X": {1: {100: _pair(pe=False)}}}, {"X": [object()]}, {}) == {"X": "NO_SAME_EXPIRY_SAME_STRIKE_CE_PE_PAIR"}

def test_unexpected_pairing_gap_reason():
    assert discovery_gap_reasons(["X"], {"X": {1: {100: _pair()}}}, {"X": [object()]}, {}) == {"X": "UNEXPECTED_PAIRING_GAP"}

def test_healthy_symbol_has_no_diagnostic():
    assert discovery_gap_reasons(["X"], {}, {}, {"X": object()}) == {}

def test_scanner_discovery_uses_helper_and_diagnostics():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "scanner.py").read_text(encoding="utf-8"))
    fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == "discover_universe")
    called = {x.func.id for x in ast.walk(fn) if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
    assert {"nearest_complete_expiry", "discovery_gap_reasons", "select_verified_universe"} <= called
