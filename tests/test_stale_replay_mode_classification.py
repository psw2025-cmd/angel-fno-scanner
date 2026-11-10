from tools.run_market_cycle import stale_or_holiday


def test_only_genuine_stale_or_holiday_can_be_classified_as_mock():
    assert stale_or_holiday("FAIL CLOSED: source timestamp out of range: 37865s")
    assert stale_or_holiday("PAPER_SCAN_SUPPRESSED:HOLIDAY:EOD")
    assert stale_or_holiday("source exchange timestamp was not verified")


def test_auth_broker_logic_and_sinks_are_not_masked():
    for text in ("403 permission denied", "BigQuery schema mismatch",
                 "Missing credentials", "SyntaxError", "AssertionError",
                 "Connection refused", "Unknown error",
                 "Scanner publication failed; cycle is unverified"):
        assert not stale_or_holiday(text), text
