import json
import pytest
from metrics import Metrics

def test_snapshot_atomic(tmp_path):
    metrics=Metrics()
    metrics.increment("ok")
    metrics.increment("ok",2)
    metrics.write(tmp_path/"telemetry.json")
    assert json.loads((tmp_path/"telemetry.json").read_text())=={"ok":3}

def test_invalid():
    with pytest.raises(ValueError):Metrics().increment("",1)
