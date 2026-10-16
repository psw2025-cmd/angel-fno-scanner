"""PAPER-only synthetic relay; no broker integration or order routing."""
import asyncio
import hmac
import math
import os
import secrets
import time
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

assert os.getenv("PAPER_MODE", "1") == "1"
assert os.getenv("LIVE_ORDER_AUTHORITY", "0") == "0"
assert os.getenv("FEED_MODE", "synthetic") == "synthetic", "Live feed disabled for this gate"
ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:8001")
ACCESS_CODE = os.getenv("DASHBOARD_ACCESS_CODE")
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_methods=["POST"], allow_headers=["Content-Type"])
tickets = {}
attempts = {}

class Login(BaseModel):
    code: str

@app.post("/session")
async def session(body: Login, request: Request):
    if not ACCESS_CODE:
        raise HTTPException(503, "Access not configured")
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    attempts[ip] = [t for t in attempts.get(ip, []) if now-t < 60]
    if len(attempts[ip]) >= 5:
        raise HTTPException(429, "Rate limited")
    attempts[ip].append(now)
    if request.headers.get("origin") != ORIGIN or not hmac.compare_digest(body.code, ACCESS_CODE):
        raise HTTPException(401, "Unauthorized")
    ticket = secrets.token_urlsafe(32)
    tickets[ticket] = now + 30
    return {"ticket": ticket, "expires_in": 30}

def normalize(token, ltp, bid, ask, volume, ts=None):
    vals = tuple(map(float, (ltp,bid,ask,volume)))
    if not all(map(math.isfinite, vals)) or vals[1]<0 or vals[2]<vals[1] or vals[3]<0:
        raise ValueError("Invalid quote")
    return dict(type="tick",token=str(token),ltp=vals[0],bid=vals[1],ask=vals[2],volume=vals[3],ts=ts or datetime.now(timezone.utc).isoformat())

@app.get("/health")
def health():
    return {"status":"ok","mode":"synthetic","paper_mode":True,"live_order_authority":False}

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    protocols = [x.strip() for x in ws.headers.get("sec-websocket-protocol","").split(",")]
    ticket = protocols[1] if len(protocols)==2 and protocols[0]=="level3" else ""
    expiry = tickets.pop(ticket, 0) if ticket else 0
    if ws.headers.get("origin") != ORIGIN or expiry <= time.monotonic():
        await ws.close(code=1008)
        return
    await ws.accept(subprotocol="level3")
    await ws.send_json({"type":"status","message":"SYNTHETIC / PAPER"})
    volume = 1000
    try:
        while True:
            volume += 25
            await ws.send_json(normalize("SYNTHETIC-CE",102.5,102.4,102.7,volume))
            await asyncio.sleep(0.25 if os.getenv("CI_FAST_TICKS")=="1" else 1)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
