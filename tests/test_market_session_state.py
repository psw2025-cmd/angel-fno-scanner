import datetime

from market_calendar import market_session_state
from angel_prediction_engine import catalyst_from_note


def test_each_minute_has_one_session_answer():
    holiday = market_session_state(datetime.datetime(2026, 10, 20, 10, 0))
    assert holiday["status"] == "HOLIDAY"
    assert holiday["name"] == "Dussehra"
    assert holiday["expect_live_scanner"] is False

    weekend = market_session_state(datetime.datetime(2026, 10, 18, 10, 0))
    assert weekend["status"] == "WEEKEND"

    before = market_session_state(datetime.datetime(2026, 10, 22, 9, 14))
    assert before["status"] == "BEFORE_OPEN"
    assert before["minute_of_day"] == 554

    opening = market_session_state(datetime.datetime(2026, 10, 22, 9, 15))
    assert opening["status"] == "OPEN"
    assert opening["phase"] == "OPENING_SCORE"

    session = market_session_state(datetime.datetime(2026, 10, 21, 12, 0))
    assert session["phase"] == "SESSION"

    pre_close = market_session_state(datetime.datetime(2026, 10, 21, 15, 40))
    assert pre_close["status"] == "OPEN"
    assert pre_close["phase"] == "PRE_CLOSE"

    after = market_session_state(datetime.datetime(2026, 10, 21, 15, 41))
    assert after["status"] == "AFTER_CLOSE"
    assert after["expect_fresh_rows"] is False

    unknown = market_session_state(datetime.datetime(2027, 1, 4, 10, 0))
    assert unknown["status"] == "UNKNOWN"


def test_january_fifteenth_is_closed_on_the_single_calendar():
    state = market_session_state(datetime.datetime(2026, 1, 15, 11, 0))
    assert state["status"] == "HOLIDAY"


def test_a_pending_contract_is_not_stored_again():
    from angel_prediction_engine import unseen_gap_picks
    picks = [
        {"symbol": "tcs", "side": "ce", "contract_symbol": "TCS27OCT262520CE"},
        {"symbol": "INFY", "side": "CE", "contract_symbol": "INFY27OCT261180CE"},
    ]
    existing = {("TCS", "CE", "TCS27OCT262520CE")}
    fresh = unseen_gap_picks(picks, existing)
    assert [p["symbol"] for p in fresh] == ["INFY"]
    assert unseen_gap_picks(picks + picks[:1], set())[0]["symbol"] == "tcs"
    assert len(unseen_gap_picks(picks + picks[:1], set())) == 2


def test_score_keeps_the_original_news_catalyst():
    note = "[OVERNIGHT GAP-UP CE] Action: ALERT | Catalyst: Order win announced | Entry: 41.40"
    assert catalyst_from_note(note) == "Order win announced"
    assert catalyst_from_note("no headline here") == ""


def test_gainers_uses_the_same_clock():
    from gainers import NSE_HOLIDAYS_2026, market_is_open
    assert "2026-01-15" in NSE_HOLIDAYS_2026
    assert market_is_open(datetime.datetime(2026, 10, 21, 15, 40)) is True
    assert market_is_open(datetime.datetime(2026, 10, 21, 15, 41)) is False
    assert market_is_open(datetime.datetime(2026, 1, 15, 11, 0)) is False


def test_monitor_day_file_matches_the_single_calendar():
    import json
    from pathlib import Path
    from market_calendar import session_day_rows
    path = Path(__file__).resolve().parents[1] / "data" / "nse_session_days_2026.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == session_day_rows()
    by_date = {row["session_date"]: row["day_status"] for row in saved}
    assert by_date["2026-10-20"] == "HOLIDAY"
    assert by_date["2026-10-21"] == "TRADING"
    assert by_date["2026-10-22"] == "TRADING"
    assert by_date["2026-01-15"] == "HOLIDAY"
    assert saved[0]["open_start_minute"] == 555
    assert saved[0]["close_end_minute"] == 940
    measures = (path.parents[1] / "ANGEL_FNO_MONITOR.SemanticModel" / "definition" / "tables" / "_Measures.tmdl").read_text(encoding="utf-8")
    for token in ("BEFORE_OPEN", "OPENING_SCORE", "SESSION", "PRE_CLOSE", "AFTER_CLOSE", "MarketCalendar[open_start_minute]"):
        assert token in measures
