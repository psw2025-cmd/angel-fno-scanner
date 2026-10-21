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
