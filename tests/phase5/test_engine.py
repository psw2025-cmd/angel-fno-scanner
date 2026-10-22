import pytest
from src.phase5_engine.validation import evaluate_gap_up
from src.phase5_engine.learning import choose
P={"published_at":"2026-10-15T10:00:00+05:30","prediction_id":"p1","track":"gap_up","symbol":"RELIANCE","target_date":"2026-10-16","previous_close":100,"predicted_gap_pct":1}
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
    with pytest.raises(ValueError, match="Invalid forecast evidence"):
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

def test_r2_metrics_prefix_matches_schema(monkeypatch):
    import json
    from pathlib import Path
    from src.phase5_engine import r2
    schema=json.loads((Path(__file__).resolve().parents[2]/"src/phase5_engine/schema.json").read_text())
    source=(Path(__file__).resolve().parents[2]/"src/phase5_engine/r2.py").read_text()
    for prefix in schema["r2_prefixes"]:
        assert repr(prefix) in source or ('"'+prefix+'"') in source

def test_gap_up_schema_matches_evaluator():
    import json
    from pathlib import Path
    schema=json.loads((Path(__file__).resolve().parents[2]/"src/phase5_engine/schema.json").read_text())
    required=set(schema["prediction_required"]) | set(schema["prediction_required_by_track"]["gap_up"])
    assert required <= set(dict(P,published_at="2026-10-15T10:00:00+05:30",predicted_return_pct=1,model_version="v1"))
    assert "predicted_gap_pct" in schema["prediction_required_by_track"]["gap_up"]
    assert "predicted_return_pct" not in schema["prediction_required_by_track"]["gap_up"]

@pytest.mark.parametrize("published", ["2026-10-15T10:00:00", "2026-10-16T00:01:00+05:30", "2026-10-17T10:00:00+05:30"])
def test_gap_up_publication_time_fail_closed(published):
    with pytest.raises(ValueError, match="Publication timestamp|precede target session"):
        evaluate_gap_up([dict(P,published_at=published)],{})

def test_gap_up_exchange_timezone_boundary():
    # Previous UTC date can already be the target trading date in India.
    with pytest.raises(ValueError, match="precede target session"):
        evaluate_gap_up([dict(P,published_at="2026-10-15T20:00:00+00:00")],{})

@pytest.mark.parametrize("field,bad", [("previous_close",0),("previous_close",float("nan")),("predicted_gap_pct",float("inf"))])
def test_invalid_forecast_rejected_before_actual_arrives(field,bad):
    with pytest.raises(ValueError, match="Invalid forecast evidence"):
        evaluate_gap_up([dict(P,**{field:bad})],{})
