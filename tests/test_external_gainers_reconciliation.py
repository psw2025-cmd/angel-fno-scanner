import pytest

from external_gainers_reconciliation import reconcile

URL = "https://www.moneycontrol.com/stocks/fno/marketstats/options/gainers/homebody.php"
AT = "2026-10-21T15:40:00+05:30"
NOW = "2026-10-22T03:30:00+05:30"


def row(strike=190, ltp=3, side="CE"):
    return dict(symbol="SAIL", expiry="2026-10-27", strike=strike, side=side, ltp=ltp)


def pick(**changes):
    p = row()
    p["issued_at"] = "2026-10-21T09:16:00+05:30"
    p.update(changes)
    return p


def run(picks, actuals, **kwargs):
    return reconcile(picks, actuals, snapshot_at=AT, source_url=URL, as_of=NOW, **kwargs)


def test_exact_contract_only_and_penny_filter():
    r = run([pick()], [row(190, 0.1), row(195, 10)])
    assert (r["exact_matches"], r["premium_eligible_matches"], r["observed_below_min_premium"]) == (1, 0, 1)
    assert r["order_authority"] == 0


def test_different_side_is_not_match():
    assert run([pick()], [row(side="PE")])["exact_matches"] == 0


@pytest.mark.parametrize("change", [
    {"issued_at": "2026-10-21T15:40:00+05:30"},
    {"issued_at": "2026-10-22T09:16:00+05:30"},
    {"issued_at": "2026-10-21T09:16:00"},
    {"strike": float("nan")},
])
def test_invalid_predictions_fail_closed(change):
    with pytest.raises(ValueError):
        run([pick(**change)], [row()])


def test_duplicate_observations_fail_closed():
    with pytest.raises(ValueError):
        run([pick()], [row(), row()])


def test_future_snapshot_fails_closed():
    with pytest.raises(ValueError):
        reconcile([pick()], [row()], snapshot_at=NOW, source_url=URL,
                  as_of="2026-10-21T15:40:00+05:30")


def test_no_predictions_gives_zero_not_success_claim():
    r = run([], [row()])
    assert r["exact_matches"] == 0 and r["advance_contracts"] == 0



def test_different_expiry_is_not_match():
    observed = row()
    observed["expiry"] = "2026-10-29"
    assert run([pick()], [observed])["exact_matches"] == 0


def test_strike_mismatch_is_not_match():
    assert run([pick()], [row(strike=191)])["exact_matches"] == 0


def test_malformed_external_row_blocks_entire_snapshot():
    with pytest.raises((ValueError, KeyError, TypeError)):
        run([pick()], [{"symbol": "SAIL", "side": "CE", "strike": 190,
                       "expiry": "2026-10-27", "ltp": "not-a-price"}])


def test_post_snapshot_advance_pick_is_not_counted():
    with pytest.raises(ValueError):
        run([pick(issued_at="2026-10-21T15:41:00+05:30")], [row()])
