"""Pure, fail-closed F&O expiry pairing and safe discovery diagnostics.

Does not call a broker, change the reviewed universe, or authorize publication.
"""
def nearest_complete_expiry(expiry_map):
    """Choose the earliest expiry with at least one same-strike CE/PE pair."""
    for expiry in sorted(expiry_map):
        complete = {
            strike: sides for strike, sides in expiry_map[expiry].items()
            if isinstance(sides, dict) and "CE" in sides and "PE" in sides
        }
        if complete:
            return expiry, complete
    return None, {}


def discovery_gap_reasons(expected_symbols, options, futures, selected):
    """Explain missing reviewed identities without exposing broker tokens or keys."""
    reasons = {}
    for symbol in sorted(set(expected_symbols) - set(selected)):
        has_options = bool(options.get(symbol))
        has_futures = bool(futures.get(symbol))
        if not has_options and not has_futures:
            reason = "NO_VALID_OPTIONS_OR_FUTURES"
        elif not has_options:
            reason = "NO_VALID_OPTIONS"
        elif not has_futures:
            reason = "NO_VALID_FUTURES"
        elif nearest_complete_expiry(options[symbol])[0] is None:
            reason = "NO_SAME_EXPIRY_SAME_STRIKE_CE_PE_PAIR"
        else:
            reason = "UNEXPECTED_PAIRING_GAP"
        reasons[symbol] = reason
    return reasons
