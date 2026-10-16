from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from market_clock import market_preflight
IST=ZoneInfo("Asia/Kolkata")
@pytest.mark.parametrize("hour,minute,allowed",[(9,14,False),(9,15,False),(9,16,True),(15,30,True),(15,31,False)])
def test_boundary(hour,minute,allowed):
    now=datetime(2026,10,16,hour,minute,tzinfo=IST)
    if allowed: assert market_preflight(now)==now
    else:
        with pytest.raises(SystemExit) as exc: market_preflight(now)
        assert exc.value.code==2
def test_weekend():
    with pytest.raises(SystemExit) as exc:market_preflight(datetime(2026,10,17,10,0,tzinfo=IST))
    assert exc.value.code==2
