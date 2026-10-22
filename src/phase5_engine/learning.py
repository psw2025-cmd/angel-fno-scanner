"""Independent walk-forward challenger selection; incumbent retained on failure."""
from math import isfinite
from .config import TRACKS,safety
def choose(track,incumbent,challenger,baseline,trial):
    safety()
    if track not in TRACKS:raise ValueError("Unknown track")
    required=("sample_count","precision","brier_score","max_drawdown","walk_forward","data_leakage_detected")
    if any(k not in m for m in (baseline,trial) for k in required):raise ValueError("Missing evidence")
    numeric=("sample_count","precision","brier_score","max_drawdown")
    if any(isinstance(m[k], bool) or not isinstance(m[k], (int,float)) or not isfinite(m[k]) for m in (baseline,trial) for k in numeric):
        raise ValueError("Non-finite or non-numeric learning evidence")
    if any(m["sample_count"] < 0 or m["sample_count"] != int(m["sample_count"])
           or not 0 <= m["precision"] <= 1 or not 0 <= m["brier_score"] <= 1
           or not 0 <= m["max_drawdown"] <= 1 for m in (baseline, trial)):
        raise ValueError("Learning metrics outside valid domains")
    if any(m["walk_forward"] not in (True, False) or not isinstance(m["walk_forward"], bool)
           or m["data_leakage_detected"] not in (True, False)
           or not isinstance(m["data_leakage_detected"], bool) for m in (baseline, trial)):
        raise ValueError("Learning verification flags must be boolean")
    eligible=(trial["sample_count"]>=100 and trial["walk_forward"] is True
              and trial["data_leakage_detected"] is False
              and trial["precision"]>baseline["precision"]
              and trial["brier_score"]<=baseline["brier_score"]
              and trial["max_drawdown"]<=baseline["max_drawdown"])
    return {"track":track,"decision":"PROMOTE_CANDIDATE" if eligible else "RETAIN_INCUMBENT","active_weights":challenger if eligible else incumbent,"rollback_weights":incumbent,"requires_versioned_r2_commit":True}
