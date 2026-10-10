import json
import pytest
from dlq_consumer import read_dead_letters,replay

def test_replay_once(tmp_path):
    path=tmp_path/"dlq.jsonl"
    path.write_text(json.dumps({"id":"x","payload":1})+"\n")
    calls=[]
    assert replay(path,lambda x:calls.append(x),tmp_path/"ack")==["x"]
    assert replay(path,lambda x:calls.append(x),tmp_path/"ack")==[]
    assert len(calls)==1

def test_invalid_id(tmp_path):
    path=tmp_path/"dlq.jsonl"
    path.write_text('{"payload":1}\n')
    with pytest.raises(ValueError):read_dead_letters(path)
