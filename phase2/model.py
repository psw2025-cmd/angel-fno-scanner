"""Deterministic, versioned paper baseline; not a trained predictive ML model."""
import math
from phase2.option_stream import enforce_paper_mode

class FeatureEngine:
    def transform(self, closing):
        enforce_paper_mode()
        rows = closing.get("contracts", [])
        output = []
        for c in rows:
            if c.get("symbol") not in ("NIFTY", "BANKNIFTY") or c.get("option_type") not in ("CE", "PE"):
                continue
            oi, volume, spread = c.get("oi"), c.get("volume"), c.get("spread_pct")
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in (oi, volume, spread)):
                continue
            output.append({"iv_rank": c.get("iv_rank"), "pcr": c.get("pcr"), "symbol": c["symbol"], "expiry": c["expiry"], "strike": c["strike"], "option_type": c["option_type"], "oi": oi, "volume": volume, "spread_pct": spread})
        if not output:
            raise ValueError("No validated liquid contracts")
        return output

class VersionedRankingModel:
    version = "paper-deterministic-baseline-v1-not-trained"
    def predict(self, features):
        enforce_paper_mode()
        scores = []
        for f in features:
            score = math.log1p(f["oi"]) + math.log1p(f["volume"]) - f["spread_pct"]
            scores.append({**f, "score": round(score, 8)})
        scores.sort(key=lambda x: (-x["score"], x["symbol"], x["expiry"], x["strike"], x["option_type"]))
        return [{**row, "rank": i} for i, row in enumerate(scores, 1)]
