"""Versioned evaluation tracks and safety configuration."""
import os
TRACKS={"gap_up":{"horizon":"T+1_open","minimum_samples":100},"breakout":{"horizon":"5-20_trading_days","minimum_samples":100},"multibagger":{"horizon":"3-12_calendar_months","minimum_samples":100}}
def safety():
    if os.getenv("PAPER_MODE","1")!="1" or os.getenv("LIVE_ORDER_AUTHORITY","0")!="0":
        raise RuntimeError("Phase 5 requires PAPER-only authority")
    return True
