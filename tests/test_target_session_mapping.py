import datetime as dt
from scripts import forward_validation as fv

def test_eod_maps_to_next_session():
    target, generated, basis = fv.resolve_target_session({'timestamp_ist':'2026-09-30T16:00:00+05:30'})
    assert target == dt.date(2026,10,1)
    assert generated.date() == dt.date(2026,9,30)
    assert basis == 'DERIVED_NEXT_NSE_SESSION'

def test_holiday_weekend_skip():
    assert fv.next_nse_session(dt.date(2026,10,1)) == dt.date(2026,10,5)
    assert fv.next_nse_session(dt.date(2026,10,2)) == dt.date(2026,10,5)

def test_stale_rejected():
    now=dt.datetime(2026,10,1,8,55,tzinfo=fv.IST)
    ok,meta=fv.validate_target_a_metadata({'prediction_generated_at':'2026-09-25T16:00:00+05:30','target_market_session_date':'2026-10-01'},now)
    assert not ok
    assert meta['reason']=='GENERATION_TOO_OLD'
