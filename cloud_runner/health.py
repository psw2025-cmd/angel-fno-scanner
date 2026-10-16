"""Sanitized runtime state; health does not claim market-data freshness."""
from datetime import datetime, timezone
from .session import enforce_safety, REQUIRED
import os

def snapshot():
    enforce_safety()
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "paper_mode": True,
        "live_order_authority": False,
        "configuration_present": all(bool(os.getenv(k)) for k in REQUIRED),
        "broker_authenticated": "NOT_TESTED",
        "tick_freshness": "NOT_TESTED",
    }
