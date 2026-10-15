"""Real-source paper close runner. Requires provider's explicit official-close attestation."""
import json
import os
from datetime import datetime, timezone
from phase2.option_stream import enforce_paper_mode
from phase2.provider import AuthorizedChainProvider
from phase2.model import FeatureEngine
from phase2.trained_model import TrainedRankingModel
from phase2.heuristic import V1HeuristicModel
from phase2.publisher import PaperPublisher
from phase2.daily_close import execute

class VerifiedClose:
    def __init__(self, provider):
        self.provider = provider
    def get_verified_official_close(self, *, symbols, timeout_seconds):
        enforce_paper_mode()
        data = [self.provider.fetch_chain(symbol) for symbol in symbols]
        if any(d.get("officially_published") is not True or d.get("quality") != "VALID" or not d.get("source_timestamp") or not d.get("source_id") for d in data):
            raise RuntimeError("Provider did not attest official publication, quality and provenance")
        timestamps = [datetime.fromisoformat(d["source_timestamp"].replace("Z", "+00:00")) for d in data]
        if any(t.tzinfo is None or t > datetime.now(timezone.utc) for t in timestamps):
            raise RuntimeError("Invalid official close timestamp")
        contracts = []
        for d in data:
            for c in d.get("contracts", []):
                contracts.append({**c, "symbol": d["symbol"]})
        if not contracts:
            raise RuntimeError("No real provider contracts")
        return {"officially_published": True, "quality": "VALID", "source_timestamp": max(timestamps).isoformat(), "sources": [{"symbol": d["symbol"], "source_id": d["source_id"], "source_timestamp": d["source_timestamp"]} for d in data], "contracts": contracts}

def main():
    enforce_paper_mode()
    provider = AuthorizedChainProvider()
    model = V1HeuristicModel() if os.getenv("PHASE2_MODEL_KIND") == "HEURISTIC" else TrainedRankingModel("phase2/artifacts")
    publisher = PaperPublisher(os.environ["PHASE2_PAPER_LEDGER_TABLE"])
    receipt = execute(VerifiedClose(provider), FeatureEngine(), model, publisher)
    print(json.dumps(receipt, sort_keys=True))

if __name__ == "__main__":
    main()
