"""Pure T+1 validation: no relay imports and no order APIs."""
from math import isfinite
from .config import safety

def evaluate_gap_up(predictions, actuals, threshold=0.5):
    safety()
    rows=[];seen=set()
    for p in predictions:
        pid=p["prediction_id"]
        if pid in seen:raise ValueError("Duplicate prediction")
        seen.add(pid)
        if p["track"]!="gap_up":raise ValueError("Wrong evaluation track")
        a=actuals.get(p["symbol"])
        if not a or not a.get("verified_open"):
            rows.append({"id":pid,"status":"PENDING_ACTUAL"});continue
        if a["session_date"]!=p["target_date"]:raise ValueError("Session mismatch")
        close=float(p["previous_close"]);opened=float(a["open_price"])
        if not all(map(isfinite,(close,opened))) or min(close,opened)<=0:raise ValueError("Invalid price")
        actual_gap=100*(opened-close)/close
        predicted=float(p["predicted_gap_pct"])
        cutoff=float(threshold)
        if not all(map(isfinite,(predicted,cutoff))):raise ValueError("Invalid prediction or threshold")
        correct=(predicted>=cutoff)==(actual_gap>=cutoff)
        rows.append({"id":pid,"status":"VALIDATED","correct":correct,"actual_gap_pct":round(actual_gap,4)})
    valid=[r for r in rows if r["status"]=="VALIDATED"]
    return {"track":"gap_up","evaluated":len(valid),"pending":len(rows)-len(valid),"accuracy_pct":round(100*sum(r["correct"] for r in valid)/len(valid),2) if valid else None,"rows":rows}
