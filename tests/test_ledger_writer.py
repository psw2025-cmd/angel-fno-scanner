import pytest
from tools.ledger_writer import append_cycle

def test_idempotent_append(tmp_path):
    path=tmp_path/"cycles.jsonl"
    cycle={"cycle_id":"c1","run_id":"r1","git_sha":"abc","status":"PASS","ts":"2026-10-10T00:00:00Z"}
    assert append_cycle(path,cycle) is True
    assert append_cycle(path,cycle) is False
    assert len(path.read_text().splitlines())==1

def test_conflict_and_missing_fields(tmp_path):
    path=tmp_path/"cycles.jsonl"
    cycle={"cycle_id":"c1","run_id":"r1","git_sha":"abc","status":"PASS","ts":"now"}
    append_cycle(path,cycle)
    with pytest.raises(ValueError):
        append_cycle(path,{**cycle,"status":"FAIL"})
    with pytest.raises(ValueError):
        append_cycle(path,{"cycle_id":"c2"})
