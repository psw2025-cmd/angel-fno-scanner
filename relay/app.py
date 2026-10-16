"""PAPER-only normalized WebSocket relay. Synthetic mode is explicit; live adapter is fail-closed until configured."""
import asyncio
import os
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()
PAPER_MODE = os.getenv("PAPER_MODE", "1")
LIVE_ORDER_AUTHORITY = os.getenv("LIVE_ORDER_AUTHORITY", "0")
assert PAPER_MODE == "1" and LIVE_ORDER_AUTHORITY == "0", "Unsafe runtime flags"
MODE = os.getenv("FEED_MODE", "synthetic")
assert MODE in ("synthetic", "live"), "Invalid feed mode"

def normalize(token, ltp, bid, ask, volume, ts=None):
    values = tuple(map(float, (ltp, bid, ask, volume)))
    if not all(__import__("math").isfinite(v) for v in values) or values[1] < 0 or values[2] < values[1] or values[3] < 0:
        raise ValueError("Invalid tick")
    return dict(type="tick", token=str(token), ltp=values[0], bid=values[1], ask=values[2], volume=values[3], ts=ts or datetime.now(timezone.utc).isoformat())

@app.get("/health")
def health():
    return {"status": "ok", "mode": MODE, "paper_mode": True, "live_order_authority": False}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    # Require an authenticated gateway to inject this header; never embed this value in public JS.
    expected = os.getenv("RELAY_GATEWAY_SECRET")
    if not expected or ws.headers.get("x-relay-gateway-secret") != expected:
        await ws.close(code=1008)
        return
    await ws.accept()
    if MODE == "live":
        await ws.send_json({"type": "status", "message": "LIVE NOT CONFIGURED: broker adapter and credential lifecycle require validation"})
        await ws.close(code=1013)
        return
    await ws.send_json({"type": "status", "message": "SYNTHETIC / PAPER"})
    try:
        volume = 1000
        while True:
            volume += 25
            await ws.send_json(normalize("SYNTHETIC-CE", 102.5, 102.4, 102.7, volume))
            await asyncio.sleep(1)
    except (WebSocketDisconnect, RuntimeError):
        pass
