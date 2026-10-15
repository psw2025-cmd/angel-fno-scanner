"""Versioned transparent paper-only heuristic, not a trained ML artifact."""
import hashlib
import inspect
import math
from phase2.option_stream import enforce_paper_mode

class V1HeuristicModel:
    version = "V1_Heuristic_Model_snapshot_v2-not-trained"
    @property
    def artifact_sha256(self):
        return hashlib.sha256(inspect.getsource(type(self)).encode()).hexdigest()
    def predict(self, features):
        enforce_paper_mode()
        output = []
        for f in features:
            pcr = f.get("pcr")
            if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in (pcr,)):
                raise ValueError("Observed PCR required; no fabricated defaults")
            if not 0 <= pcr <= 10:
                raise ValueError("PCR out of range")
            if f.get("option_type") not in ("CE", "PE"):
                raise ValueError("Invalid option type")
            if f["option_type"] == "CE":
                imbalance = max(0.0, min(1.0, (pcr - 1.0) / 0.5))
            else:
                imbalance = max(0.0, min(1.0, (1.0 - pcr) / 0.5))
            volume_quality = min(1.0, math.log1p(f["volume"]) / math.log1p(10000))
            liquid = f["oi"] >= 1000 and f["volume"] >= 100 and f["spread_pct"] <= 2
            score = round((0.7 * imbalance + 0.3 * volume_quality) * (1 if liquid else 0), 8)
            output.append({**f, "score": score, "model_kind": "HEURISTIC_NOT_ML"})
        output.sort(key=lambda r: (-r["score"], r["symbol"], r["expiry"], r["strike"], r["option_type"]))
        return [{**r, "rank": i} for i, r in enumerate(output, 1)]
