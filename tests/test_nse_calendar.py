from datetime import date
import pytest
from nse_calendar import trading_status, previous_trading_day, load_calendar

def test_official_2026_calendar_and_special_closure():
    assert len(load_calendar()["holidays"]) == 16
    assert trading_status(date(2026,1,15))["market_closed"]
    assert trading_status(date(2026,3,3))["market_closed"]
    assert trading_status(date(2026,10,20))["market_closed"]
    assert not trading_status(date(2026,10,15))["market_closed"]

def test_weekend_and_previous_actual_trading_day():
    assert trading_status(date(2026,11,8))["market_closed"]
    assert previous_trading_day(date(2026,10,21))==date(2026,10,19)
    assert previous_trading_day(date(2026,1,16))==date(2026,1,14)
    assert previous_trading_day(date(2026,11,11))==date(2026,11,9)

def test_unknown_year_fails_closed():
    with pytest.raises(RuntimeError,match="does not cover"):
        trading_status(date(2027,1,4))
