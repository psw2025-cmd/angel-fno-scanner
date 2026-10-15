"""Read-only market data adapter. Provider implements fetch_chain(symbol)."""
import os
import random
import time
from datetime import datetime, timezone

SYMBOLS = frozenset(("NIFTY", "BANKNIFTY"))

def enforce_paper_mode():
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY") != "0":
        raise RuntimeError("Phase 2 requires PAPER_MODE=1 and LIVE_ORDER_AUTHORITY=0")

class RateLimited(Exception):
    def __init__(self, retry_after=None):
        super().__init__("Provider rate limit")
        self.retry_after = retry_after

class OptionStream:
    def __init__(self, provider, *, max_age_seconds=30, sleep=time.sleep):
        enforce_paper_mode()
        self.provider, self.max_age_seconds, self.sleep = provider, max_age_seconds, sleep

    def fetch(self, symbol):
        enforce_paper_mode()
        if symbol not in SYMBOLS:
            raise ValueError("Unsupported underlying")
        for attempt in range(5):
            try:
                return self.validate(symbol, self.provider.fetch_chain(symbol))
            except RateLimited as exc:
                if attempt == 4:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else 2 ** attempt
                self.sleep(min(max(float(delay), 1), 60))
            except (ConnectionError, TimeoutError):
                if attempt == 4:
                    raise
                self.sleep(min(2 ** attempt, 30) + random.uniform(0, .5))
        raise RuntimeError("Unreachable")

    def validate(self, symbol, payload):
        if payload.get("symbol") != symbol:
            raise ValueError("Underlying mismatch")
        stamp = datetime.fromisoformat(payload["source_timestamp"].replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Timezone required")
        age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
        if not -5 <= age <= self.max_age_seconds:
            raise ValueError("Stale or future market data")
        contracts = payload.get("contracts")
        if not isinstance(contracts, list) or not contracts:
            raise ValueError("Empty chain")
        identities = set()
        for item in contracts:
            key = (item["expiry"], item["strike"], item["option_type"])
            if key in identities or item["option_type"] not in ("CE", "PE") or not isinstance(item["strike"], (int, float)) or isinstance(item["strike"], bool) or item["strike"] <= 0:
                raise ValueError("Invalid or duplicate contract")
            identities.add(key)
            for greek in ("delta", "gamma", "theta", "vega", "iv"):
                item.setdefault(greek, None)
        return {"symbol": symbol, "source_timestamp": stamp.isoformat(), "contracts": contracts, "quality": "VALID"}
