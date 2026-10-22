import pytest
from src.phase5_engine.validation import evaluate_gap_up
from src.phase5_engine.learning import choose
P={"prediction_id":"p1","track":"gap_up","symbol":"RELIANCE","target_date":"2026-10-16","previous_close":100,"predicted_gap_pct":1}
def test_pending_not_failure():
    r=evaluate_gap_up([P],{})
    assert r["accuracy_pct"] is None and r["pending"]==1
def test_gap_up_accuracy():
    a={"RELIANCE":{"verified_open":True,"session_date":"2026-10-16","open_price":101}}
    assert evaluate_gap_up([P],a)["accuracy_pct"]==100
def test_duplicate_rejected():
    with pytest.raises(ValueError):evaluate_gap_up([P,P],{})
def test_no_leakage_and_rollback():
    m={"sample_count":120,"precision":.7,"brier_score":.1,"max_drawdown":.1,"walk_forward":True,"data_leakage_detected":False}
    n=dict(m,precision=.8,data_leakage_detected=True)
    r=choose("gap_up",{"volume":1},{"volume":2},m,n)
    assert r["decision"]=="RETAIN_INCUMBENT" and r["rollback_weights"]=={"volume":1}
def test_minimum_sample():
    m={"sample_count":120,"precision":.7,"brier_score":.1,"max_drawdown":.1,"walk_forward":True,"data_leakage_detected":False}
    assert choose("gap_up",1,2,m,dict(m,sample_count=99,precision=.8))["active_weights"]==1

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_forecast_rejected(bad):
    a={"RELIANCE":{"verified_open":True,"session_date":"2026-10-16","open_price":101}}
    with pytest.raises(ValueError, match="Invalid prediction or threshold"):
        evaluate_gap_up([dict(P,predicted_gap_pct=bad)],a)

def test_nonfinite_threshold_rejected():
    a={"RELIANCE":{"verified_open":True,"session_date":"2026-10-16","open_price":101}}
    with pytest.raises(ValueError, match="Invalid prediction or threshold"):
        evaluate_gap_up([P],a,threshold=float("nan"))

@pytest.mark.parametrize("field", ["sample_count","precision","brier_score","max_drawdown"])
@pytest.mark.parametrize("bad", [float("nan"),float("inf"),float("-inf"),True,"invalid"])
def test_invalid_learning_evidence_rejected(field,bad):
    m={"sample_count":120,"precision":.7,"brier_score":.1,"max_drawdown":.1,"walk_forward":True,"data_leakage_detected":False}
    with pytest.raises(ValueError,match="Non-finite or non-numeric"):
        choose("gap_up",1,2,m,dict(m,**{field:bad}))
