from tools.slo_monitor import evaluate

def test_slo_no_cycles_not_success():
    assert evaluate([])["observed_success_rate"] is None

def test_slo_three_failures_opens_circuit():
    assert evaluate([{"verified_count":218,"total":219}]*3)["circuit_open"]

def test_slo_good_cycle_resets_streak():
    assert not evaluate([{"verified_count":218,"total":219}]*3+[{"verified_count":219,"total":219}])["circuit_open"]
