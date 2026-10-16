import os
os.environ.update(PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0", FEED_MODE="synthetic")
import pytest
from smartapi_adapter import extract_quote
from app import normalize


def snap_quote(**over):
    """Shape produced by SmartApi.smartWebSocketV2 for subscription mode 3."""
    msg = {
        "subscription_mode": 3,
        "exchange_type": 1,
        "token": "2885",
        "last_traded_price": 134550,
        "volume_trade_for_the_day": 4521000,
        "best_5_buy_data": [
            {"flag": 0, "quantity": 100, "price": 134540, "no of orders": 3},
            {"flag": 0, "quantity": 80, "price": 134530, "no of orders": 2},
        ],
        "best_5_sell_data": [
            {"flag": 1, "quantity": 90, "price": 134560, "no of orders": 4},
            {"flag": 1, "quantity": 70, "price": 134570, "no of orders": 1},
        ],
    }
    msg.update(over)
    return msg


def test_real_sdk_shape_is_normalized():
    ltp, bid, ask, volume = extract_quote(snap_quote(), "2885")
    assert (ltp, bid, ask, volume) == (1345.50, 1345.40, 1345.60, 4521000.0)
    tick = normalize("2885", ltp, bid, ask, volume)
    assert tick["type"] == "tick" and tick["token"] == "2885"
    assert tick["ask"] - tick["bid"] == pytest.approx(0.20)


def test_best_bid_and_ask_regardless_of_order():
    msg = snap_quote(best_5_buy_data=[
        {"flag": 0, "quantity": 1, "price": 134500, "no of orders": 1},
        {"flag": 0, "quantity": 1, "price": 134540, "no of orders": 1},
    ])
    assert extract_quote(msg, "2885")[1] == 1345.40


def test_other_token_ignored():
    assert extract_quote(snap_quote(token="1333"), "2885") is None


def test_empty_depth_not_published():
    zero = [{"flag": 0, "quantity": 0, "price": 0, "no of orders": 0}]
    assert extract_quote(snap_quote(best_5_buy_data=zero), "2885") is None
    assert extract_quote(snap_quote(best_5_sell_data=[]), "2885") is None


def test_malformed_payload_raises_keyerror_naming_field():
    msg = snap_quote()
    del msg["volume_trade_for_the_day"]
    with pytest.raises(KeyError, match="volume_trade_for_the_day"):
        extract_quote(msg, "2885")
    # The pre-fix key must no longer be what the adapter depends on.
    legacy = snap_quote()
    assert "best_5_data" not in legacy
    assert extract_quote(legacy, "2885") is not None
