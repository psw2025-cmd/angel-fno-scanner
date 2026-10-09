from tools.cycle_evidence import compare_cycle_evidence
META = dict(run_id="r", git_sha="s", cycle_id="c", writer_id="w", source_timestamp="t")
def test_missing_bigquery_blocks_publication():
    ok, reason = compare_cycle_evidence(META, sheets=META, bigquery=None, git=META)
    assert not ok and "BigQuery" in reason
def test_missing_sheet_blocks_publication():
    ok, reason = compare_cycle_evidence(META, sheets=None, bigquery=META, git=META)
    assert not ok and "Sheets" in reason
