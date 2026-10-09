from tools.cycle_evidence import compare_cycle_evidence
META = dict(run_id="r", git_sha="s", cycle_id="c", writer_id="w", source_timestamp="t")
def test_matching_evidence():
    assert compare_cycle_evidence(META, sheets=META, bigquery=META, git=META)[0]
def test_run_id_mismatch():
    assert not compare_cycle_evidence(META, sheets={**META, "run_id":"wrong"}, bigquery=META, git=META)[0]
