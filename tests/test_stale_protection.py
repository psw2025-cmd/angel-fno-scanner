import datetime as dt
import pytest
from tools.check_freshness import validate

META = {"run_id": "r1", "git_sha": "sha1", "cycle_id": "c1"}
NOW = dt.datetime(2026, 10, 9, 10, 0, tzinfo=dt.timezone.utc)

def stamp(seconds):
    return (NOW - dt.timedelta(seconds=seconds)).isoformat()

def test_open_rejects_stale_300_seconds():
    with pytest.raises(ValueError, match="out of range"):
        validate(stamp(300), "r1", "sha1", "c1", "OPEN", expected=META, now=NOW)

def test_eod_accepts_1800_seconds():
    assert validate(stamp(1800), "r1", "sha1", "c1", "EOD", expected=META, now=NOW)["status"] == "PASS"

def test_identity_mismatch_fails_closed():
    with pytest.raises(ValueError, match="run_id mismatch"):
        validate(stamp(20), "wrong", "sha1", "c1", "OPEN", expected=META, now=NOW)

def test_missing_authoritative_metadata_fails_closed():
    with pytest.raises(ValueError, match="metadata missing"):
        validate(stamp(20), "r1", "sha1", "c1", "OPEN", expected=None, now=NOW)
