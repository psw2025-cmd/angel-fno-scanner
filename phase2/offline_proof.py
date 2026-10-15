"""Deterministic fixture-only end-to-end pipeline test; no market-data or BigQuery claims."""
import json
import os
from phase2.option_stream import enforce_paper_mode
from phase2.daily_close import execute
from phase2.model import FeatureEngine
from phase2.heuristic import V1HeuristicModel
from phase2.local_publisher import LocalArtifactPublisher

class FixtureClose:
    def get_verified_official_close(self, *, symbols, timeout_seconds):
        if tuple(symbols) != ("NIFTY", "BANKNIFTY"):
            raise ValueError("Fixture symbols changed")
        rows = []
        for symbol in symbols:
            for option_type, pcr in (("CE", 1.2), ("PE", 0.8)):
                rows.append({"symbol": symbol, "option_type": option_type,
                             "expiry": "2099-12-31", "strike": 25000 if symbol == "NIFTY" else 50000,
                             "oi": 2000, "volume": 300, "spread_pct": 1.0, "pcr": pcr,
                             "iv_rank": None})
        return {"officially_published": True, "quality": "VALID",
                "source_timestamp": "2026-01-01T00:00:00+00:00",
                "source_kind": "SYNTHETIC_TEST_FIXTURE_NOT_MARKET_DATA",
                "contracts": rows}

def main():
    enforce_paper_mode()
    if os.getenv("PHASE2_SOURCE_KIND") != "SYNTHETIC_TEST_FIXTURE_NOT_MARKET_DATA":
        raise RuntimeError("Fixture runner requires explicit synthetic source labeling")
    receipt = execute(FixtureClose(), FeatureEngine(), V1HeuristicModel(), LocalArtifactPublisher())
    if receipt["status"] != "LOCAL_ARTIFACT_ONLY_NOT_INSERTED":
        raise RuntimeError("Unexpected publication status")
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    main()
