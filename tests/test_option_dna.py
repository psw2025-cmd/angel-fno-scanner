import pytest
from phase2.option_dna import snapshot_dna, structure_watch

def quote(bid=90,ask=100,oi=100,volume=500):
    return {"depth":{"buy":[{"price":bid}],"sell":[{"price":ask}]},"openInterest":oi,"tradeVolume":volume,"exchFeedTime":"15-Oct-2026 15:40:00"}

def test_spread_and_ratio_are_observed_not_inferred():
    x=snapshot_dna(quote())
    assert x["spread_pct"]==round(200*10/190,8)
    assert x["volume_oi_ratio"]==5
    assert "WIDE_SPREAD_3PCT" in x["flags"]
    assert "VOLUME_OI_RATIO_HIGH_3X_NOT_OI_CHANGE" in x["flags"]
    assert x["iv"] is None and x["theta"] is None
    assert x["oi_change_pct"] is None

def test_shock_requires_prior_and_real_oi_delta():
    q=quote(90,100,80,200)
    x=snapshot_dna(q,prior={"spread_pct":1,"oi":100})
    assert "SPREAD_SHOCK_2X_PRIOR" in x["flags"]
    assert "OI_FALL_20PCT_WITH_VOLUME" in x["flags"]
    assert x["oi_change_pct"]==-20
    assert "SPREAD_SHOCK_2X_PRIOR" not in snapshot_dna(q)["flags"]

def test_missing_or_crossed_depth_fails_closed():
    with pytest.raises(ValueError): snapshot_dna(quote(100,90))
    with pytest.raises(ValueError): snapshot_dna({"depth":{}})

def test_structure_is_unconfirmed_selected_strike_watch():
    rows=[{"symbol":"NIFTY","expiry":"2026-10-27","option_type":"CE","oi":100},
          {"symbol":"NIFTY","expiry":"2026-10-27","option_type":"PE","oi":200}]
    x=structure_watch(rows)[0]
    assert x["state"]=="POTENTIAL_BOTTOM_WATCH_OI_IMBALANCE_ONLY"
    assert x["confirmed_reversal"] is False
