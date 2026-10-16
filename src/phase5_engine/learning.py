"""Independent walk-forward challenger selection; incumbent retained on failure."""
from .config import TRACKS,safety
def choose(track,incumbent,challenger,baseline,trial):
    safety()
    if track not in TRACKS:raise ValueError("Unknown track")
    required=("sample_count","precision","brier_score","max_drawdown","walk_forward","data_leakage_detected")
    if any(k not in m for m in (baseline,trial) for k in required):raise ValueError("Missing evidence")
    eligible=(trial["sample_count"]>=100 and trial["walk_forward"] is True
              and trial["data_leakage_detected"] is False
              and trial["precision"]>baseline["precision"]
              and trial["brier_score"]<=baseline["brier_score"]
              and trial["max_drawdown"]<=baseline["max_drawdown"])
    return {"track":track,"decision":"PROMOTE_CANDIDATE" if eligible else "RETAIN_INCUMBENT","active_weights":challenger if eligible else incumbent,"rollback_weights":incumbent,"requires_versioned_r2_commit":True}
