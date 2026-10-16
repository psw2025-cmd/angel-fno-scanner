import os
os.environ.update(PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0", FEED_MODE="synthetic", FRONTEND_ORIGIN="http://127.0.0.1:8001", DASHBOARD_ACCESS_CODE="ci-only-synthetic-test")
import pytest
from fastapi.testclient import TestClient
from app import app, normalize

def test_spread_and_volume():
    a=normalize("TEST",100,99,101,1000)
    b=normalize("TEST",100,99.5,100.5,1030)
    assert a["ask"]-a["bid"]==2
    assert b["ask"]-b["bid"]==1
    assert b["volume"]-a["volume"]==30

def test_bad_quote():
    with pytest.raises(ValueError): normalize("TEST",100,102,101,1000)

def test_authentication_and_stream():
    with TestClient(app) as c:
        with pytest.raises(Exception):
            with c.websocket_connect("/ws",headers={"origin":"http://127.0.0.1:8001"}): pass
        bad=c.post("/session",json={"code":"bad"},headers={"origin":"http://127.0.0.1:8001"})
        assert bad.status_code==401
        good=c.post("/session",json={"code":"ci-only-synthetic-test"},headers={"origin":"http://127.0.0.1:8001"})
        assert good.status_code==200
        ticket=good.json()["ticket"]
        with c.websocket_connect("/ws",headers={"origin":"http://127.0.0.1:8001"},subprotocols=["level3",ticket]) as ws:
            assert ws.receive_json()["message"]=="SYNTHETIC / PAPER"
            a=ws.receive_json();b=ws.receive_json()
            assert a["type"]=="tick" and b["volume"]-a["volume"]==25
        with pytest.raises(Exception):
            with c.websocket_connect("/ws",headers={"origin":"http://127.0.0.1:8001"},subprotocols=["level3",ticket]): pass
