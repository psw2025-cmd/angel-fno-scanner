"""Public NSE option-chain snapshot adapter. No synthetic substitution or official-close claim."""
import hashlib
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from phase2.option_stream import enforce_paper_mode

URL = "https://www.nseindia.com/api/option-chain-indices"
IST = ZoneInfo("Asia/Kolkata")

class NSEPublicChainProvider:
    def __init__(self, session=None):
        enforce_paper_mode()
        self.session = session or requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/option-chain"})
    def fetch_chain(self, symbol):
        enforce_paper_mode()
        if symbol not in ("NIFTY", "BANKNIFTY"):
            raise ValueError("Unsupported underlying")
        response = self.session.get(URL, params={"symbol": symbol}, timeout=(10, 25))
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict) or not isinstance(raw.get("records"), dict):
            raise ValueError("NSE response is not a valid option-chain document")
        records = raw["records"]
        if records.get("underlying") != symbol:
            raise ValueError("NSE underlying identity mismatch")
        stamp = datetime.strptime(records["timestamp"], "%d-%b-%Y %H:%M:%S").replace(tzinfo=IST)
        now = datetime.now(IST)
        if stamp.date() != now.date() or stamp > now:
            raise ValueError("NSE chain is not from today's session")
        if not (stamp.hour > 15 or (stamp.hour == 15 and stamp.minute >= 30)):
            raise ValueError("NSE chain timestamp precedes normal market close")
        raw_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        total_ce = sum(x.get("CE", {}).get("openInterest", 0) for x in records.get("data", []))
        total_pe = sum(x.get("PE", {}).get("openInterest", 0) for x in records.get("data", []))
        if not total_ce or not total_pe:
            raise ValueError("NSE OI unavailable")
        pcr = total_pe / total_ce
        contracts = []
        for row in records.get("data", []):
            for side in ("CE", "PE"):
                c = row.get(side)
                if not isinstance(c, dict):
                    continue
                bid, ask = c.get("bidprice"), c.get("askPrice")
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in (bid, ask)) or ask < bid:
                    continue
                midpoint = (bid + ask) / 2
                spread = 100 * (ask - bid) / midpoint
                oi, volume = c.get("openInterest"), c.get("totalTradedVolume")
                if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in (oi, volume)):
                    continue
                contracts.append({"symbol": symbol, "option_type": side, "expiry": row["expiryDate"], "strike": row["strikePrice"], "oi": oi, "volume": volume, "spread_pct": spread, "pcr": pcr, "iv_rank": None})
        if not contracts:
            raise ValueError("NSE response contains no executable-quote contracts")
        return {"symbol": symbol, "source_timestamp": stamp.isoformat(), "source_id": URL + "?symbol=" + symbol, "raw_sha256": raw_hash, "quality": "VALID", "officially_published": True, "source_kind": "NSE_PUBLIC_POST_CLOSE_SNAPSHOT_NOT_OFFICIAL_SETTLEMENT", "contracts": contracts}
