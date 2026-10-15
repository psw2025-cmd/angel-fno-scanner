import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from phase2.option_stream import OptionStream, RateLimited, enforce_paper_mode
from phase2.daily_close import execute, canonical_hash
from tools.phase2_schema_migration import plan

@pytest.fixture(autouse=True)
def paper(monkeypatch):
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "0")

def chain():
    return {"symbol": "NIFTY", "source_timestamp": datetime.now(timezone.utc).isoformat(),
            "contracts": [{"expiry": "2026-10-29", "strike": 25000, "option_type": "CE"}]}

def test_safety(monkeypatch):
    enforce_paper_mode()
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "1")
    with pytest.raises(RuntimeError):
        enforce_paper_mode()

def test_stream_and_identity():
    class Provider:
        def fetch_chain(self, symbol):
            return chain()
    data = OptionStream(Provider()).fetch("NIFTY")
    assert data["contracts"][0]["delta"] is None
    with pytest.raises(ValueError):
        OptionStream(Provider()).fetch("BANKNIFTY")

def test_rate_limit_reconnect():
    class Provider:
        calls = 0
        def fetch_chain(self, symbol):
            self.calls += 1
            if self.calls == 1:
                raise RateLimited(1)
            return chain()
    p = Provider()
    delays = []
    assert OptionStream(p, sleep=delays.append).fetch("NIFTY")["quality"] == "VALID"
    assert p.calls == 2 and delays == [1]

def test_migration_plan():
    root = Path(__file__).resolve().parents[1]
    contract = json.loads((root / "schemas/option_predictions_live.json").read_text())
    baseline = [f for f in contract if f["name"] not in ("cycle_id", "data_freshness_status", "git_sha", "run_id", "source_timestamp", "writer_id")]
    assert len(plan(baseline, contract)["missing"]) == 6
    with pytest.raises(ValueError):
        plan(baseline + [{"name": "run_id", "type": "INT64"}], contract)

def test_paper_prediction():
    class Close:
        def get_verified_official_close(self, **kwargs):
            return {"officially_published": True, "quality": "VALID", "source_timestamp": "2026-10-15T10:00:00+00:00"}
    class Features:
        def transform(self, closing):
            return [{"signal": 1}]
    class Model:
        version = "test-model-v1"
        def predict(self, features):
            return [{"symbol": "NIFTY", "rank": 1}]
    class Publisher:
        def publish_once(self, prediction):
            assert prediction["mode"] == "PAPER" and prediction["live_order_authority"] == 0
            return {"prediction_hash": prediction["prediction_hash"]}
    assert len(execute(Close(), Features(), Model(), Publisher())["prediction_hash"]) == 64


def test_deterministic_paper_replay():
    class Close:
        def get_verified_official_close(self, **kwargs):
            return {'officially_published': True, 'quality': 'VALID', 'source_timestamp': '2026-10-15T10:00:00+00:00'}
    class Features:
        def transform(self, closing):
            return [{'signal': 1}]
    class Model:
        version = 'test-v1'
        def predict(self, features):
            return [{'symbol': 'NIFTY', 'rank': 1}]
    class Publisher:
        def publish_once(self, prediction):
            return {'prediction_hash': prediction['prediction_hash']}
    first = execute(Close(), Features(), Model(), Publisher())
    second = execute(Close(), Features(), Model(), Publisher())
    assert first['prediction_hash'] == second['prediction_hash']
