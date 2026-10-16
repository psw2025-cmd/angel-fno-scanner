import os
os.environ["PAPER_MODE"]="1"
os.environ["LIVE_ORDER_AUTHORITY"]="0"
from app import normalize, app
from fastapi.testclient import TestClient
def test_spread_and_volume():
    a=normalize("TEST",100,99,101,1000)
    b=normalize("TEST",100,99.5,100.5,1030)
    assert a["ask"]-a["bid"]==2
    assert round(b["ask"]-b["bid"],2)==1
    assert b["volume"]-a["volume"]==30
def test_reject_bad_quote():
    import pytest
    with pytest.raises(ValueError): normalize("TEST",100,102,101,1000)
def test_gateway_rejects_anonymous():
    with TestClient(app) as c:
        import pytest
        with pytest.raises(Exception): 
            with c.websocket_connect("/ws"): pass
