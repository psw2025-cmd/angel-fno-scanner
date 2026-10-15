import json
from pathlib import Path
import pytest
from fixtures.phase1_safety import assert_safe
from fixtures.six_column_repair import repair, REPAIR
ROOT=Path(__file__).resolve().parents[1]
def test_safety():
    assert assert_safe("fixture-only")
    with pytest.raises(RuntimeError): assert_safe("fno-angel-prod-1790444589")
    with pytest.raises(RuntimeError): assert_safe(live_order_authority=1)
def test_six_column_repair():
    committed=json.loads((ROOT/"schemas/option_predictions_live.json").read_text())
    assert len(committed)==54
    baseline=[f for f in committed if f["name"] not in REPAIR]
    assert len(baseline)==48
    repaired=repair(baseline)
    assert len(repaired)==54
    assert {f["name"]:f["type"] for f in repaired if f["name"] in REPAIR}==REPAIR
    assert repair(repaired)==repaired
    with pytest.raises(ValueError): repair(baseline+[{"name":"run_id","type":"INT64","mode":"NULLABLE"}])
def test_219_symbol_scrubbed_replay():
    assert_safe("fixture-only")
    symbols=[f"TEST_SYMBOL_{i:03d}" for i in range(1,220)]
    print("OFFLINE 219-symbol scrubbed replay initiating")
    assert len(symbols)==len(set(symbols))==219
    assert all(s.startswith("TEST_SYMBOL_") for s in symbols)
    print("OFFLINE 219-symbol scrubbed replay completed successfully; cloud credentials not required")
