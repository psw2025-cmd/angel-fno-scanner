#!/usr/bin/env python3
"""
tools/profile_scanner.py
100-Year Autonomy Audit — cProfile Performance Bottleneck Profiler
Profiles quantitative Greek math, universe contract mapping, and Black-76 pricing.
Outputs docs/100_year_local_audit/cprofile_analysis.txt
"""

import cProfile
import pstats
import io
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
OUTPUT_FILE = REPO_ROOT / "docs" / "100_year_local_audit" / "cprofile_analysis.txt"

def run_profile():
    pr = cProfile.Profile()
    pr.enable()

    # Import and run key computation paths
    import math
    from gainers import black76_price, implied_vol, black76_greeks, market_is_open
    from universe_contract import select_verified_universe, verified_symbols

    # 1. Benchmark 1,000 iterations of Black-76 pricing and IV solve
    for i in range(1000):
        s = 2000.0 + (i % 100)
        k = 2000.0
        r = 0.07
        t = 15.0 / 365.0
        price = 45.0 + (i % 20)
        _ = black76_price(s, k, t, r, 0.25, is_call=True)
        _ = implied_vol(price, s, k, t, r, is_call=True)
        _ = black76_greeks(s, k, t, r, 0.25, is_call=True)

    # 2. Universe mapping
    sym_dict = {s: True for s in verified_symbols()}
    _ = select_verified_universe(sym_dict)

    pr.disable()
    s = io.StringIO()
    sortby = pstats.SortKey.CUMULATIVE
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(30)

    output = s.getvalue()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"[OK] Profiling complete. Top 30 calls saved to {OUTPUT_FILE}")
    print(output[:1200])

if __name__ == "__main__":
    run_profile()
