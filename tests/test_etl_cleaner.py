from etl_cleaner import validate_rows

def test_rejects_and_accepts(tmp_path):
    accepted,rejected=validate_rows([{"symbol":"NIFTY","price":2.0},{"symbol":"","price":"2"}],["symbol","price"],{"price":float},tmp_path/"rejects.jsonl")
    assert len(accepted)==1
    assert len(rejected)==1
    assert "missing symbol" in rejected[0]["errors"]
    assert (tmp_path/"rejects.jsonl").exists()

def test_non_mapping():
    assert len(validate_rows([None],["symbol"])[1])==1
