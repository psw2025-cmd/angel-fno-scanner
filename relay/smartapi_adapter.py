"""Angel SmartAPI single-token market-data adapter. PAPER-only; no order APIs."""
import asyncio
import logging
import os
import threading
from datetime import datetime, timezone

log = logging.getLogger("level3.smartapi")
REQUIRED = ("ANGEL_API_KEY","ANGEL_CLIENT_CODE","ANGEL_PIN","ANGEL_TOTP_SEED","ANGEL_EXCHANGE_TYPE","ANGEL_SYMBOL_TOKEN")
def config():
    missing=[key for key in REQUIRED if not os.getenv(key)]
    if missing: raise RuntimeError("Missing SmartAPI configuration: "+", ".join(missing))
    if os.getenv("PAPER_MODE")!="1" or os.getenv("LIVE_ORDER_AUTHORITY")!="0":
        raise RuntimeError("Unsafe authority flags")
    return {key:os.environ[key] for key in REQUIRED}

async def stream_live(send_tick, normalize):
    """Run blocking SDK in a thread and pass normalized ticks into async relay."""
    c=config()
    from SmartApi import SmartConnect
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    import pyotp
    session_client=SmartConnect(api_key=c["ANGEL_API_KEY"])
    session=session_client.generateSession(c["ANGEL_CLIENT_CODE"],c["ANGEL_PIN"],pyotp.TOTP(c["ANGEL_TOTP_SEED"]).now())
    data=session.get("data") if isinstance(session,dict) else None
    if not data or not data.get("jwtToken") or not data.get("feedToken"):
        raise RuntimeError("SmartAPI session authentication failed")
    websocket=SmartWebSocketV2(data["jwtToken"],c["ANGEL_API_KEY"],c["ANGEL_CLIENT_CODE"],data["feedToken"])
    loop=asyncio.get_running_loop()
    queue=asyncio.Queue(maxsize=100)
    stopped=threading.Event()
    exchange=int(c["ANGEL_EXCHANGE_TYPE"])
    token=c["ANGEL_SYMBOL_TOKEN"]
    def on_open(ws):
        log.info("smartapi_connected exchange=%s token=%s",exchange,token)
        websocket.subscribe("level3-paper",3,[{"exchangeType":exchange,"tokens":[token]}])
    def on_data(ws,message):
        log.info("smartapi_raw_tick_received token=%s timestamp=%s",message.get("token"),datetime.now(timezone.utc).isoformat())
        try:
            if str(message.get("token"))!=token:return
            # SmartAPI SNAP_QUOTE prices are scaled by 100; reject absent bid/ask/volume.
            depth=message["best_5_data"]
            bids=[x for x in depth if x.get("buy_sell_indicator")==1]
            asks=[x for x in depth if x.get("buy_sell_indicator")==2]
            if not bids or not asks:return
            bid=float(bids[0]["price"])/100
            ask=float(asks[0]["price"])/100
            tick=normalize(token,float(message["last_traded_price"])/100,bid,ask,float(message["volume_trade_for_the_day"]),datetime.now(timezone.utc).isoformat())
            log.info("smartapi_normalized_tick token=%s ts=%s bid=%s ask=%s volume=%s",token,tick["ts"],bid,ask,tick["volume"])
            loop.call_soon_threadsafe(enqueue,tick)
        except (KeyError,ValueError,TypeError,IndexError) as exc:
            log.warning("smartapi_tick_rejected reason=%s",type(exc).__name__)
    def enqueue(tick):
        if not queue.full():queue.put_nowait(tick)
    def on_error(ws,error):log.error("smartapi_socket_error type=%s",type(error).__name__)
    def on_close(ws, *args):
        log.info("WebSocket closed")
    websocket.on_open=on_open
    websocket.on_data=on_data
    websocket.on_error=on_error
    websocket.on_close=on_close
    thread=threading.Thread(target=websocket.connect,daemon=True)
    thread.start()
    try:
        while not stopped.is_set():
            tick=await asyncio.wait_for(queue.get(),timeout=30)
            await send_tick(tick)
    finally:
        stopped.set()
        websocket.close_connection()
