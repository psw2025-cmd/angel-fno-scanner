import pytest
from tools.exchange_timestamp import get_exchange_timestamp

def test_exchange_timestamp_from_epoch():
    assert get_exchange_timestamp({"exchFeedTime": 1760000000}).startswith("2025-10-09T")

def test_processing_timestamp_not_substituted():
    with pytest.raises(ValueError, match="exchFeedTime"):
        get_exchange_timestamp({"ltp": 100, "timestamp": "2026-10-09 10:00:00"})

def test_naive_exchange_timestamp_rejected():
    with pytest.raises(ValueError, match="timezone"):
        get_exchange_timestamp({"exchFeedTime": "2026-10-09 10:00:00"})


def test_angel_full_exchange_local_format():
    assert get_exchange_timestamp({"exchFeedTime":"09-Oct-2026 12:00:00"}) == "2026-10-09T06:30:00+00:00"
