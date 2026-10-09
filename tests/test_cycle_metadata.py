import json
import pytest
from tools.cycle_metadata import write_cycle_metadata

def test_oldest_tick_is_selected(tmp_path):
    meta = write_cycle_metadata([{"exchFeedTime":1760000300},{"exchFeedTime":1760000000}],
        run_id="r", git_sha="sha", market_session="EOD", path=tmp_path/"meta.json")
    assert meta["source_timestamp"].startswith("2025-10-09T")
    assert meta["verified_quote_count"] == 2

def test_missing_quote_tick_fails_without_file(tmp_path):
    path = tmp_path/"meta.json"
    with pytest.raises(ValueError):
        write_cycle_metadata([{"exchFeedTime":1760000300},{"ltp":1}], run_id="r",
            git_sha="sha", market_session="OPEN", path=path)
    assert not path.exists()


def test_219_unique_quote_coverage_required():
    from tools.cycle_metadata import generate_cycle_metadata
    quotes = [{"symbolToken":str(i), "exchFeedTime":1760000000} for i in range(219)]
    assert generate_cycle_metadata(quotes,"r","sha","EOD")["verified_count"] == 219
    with pytest.raises(ValueError, match="Expected 219"):
        generate_cycle_metadata(quotes[:-1],"r","sha","EOD")
    with pytest.raises(ValueError, match="distinct"):
        generate_cycle_metadata(quotes[:-1] + [quotes[0]],"r","sha","EOD")
