"""Deterministic offline freshness tests; no market or broker claims."""
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/monitoring/publication_freshness.py"
spec = importlib.util.spec_from_file_location("publication_freshness", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_old_connected_heartbeat_fails_closed():
    now = datetime(2026, 11, 26, 8, 30, tzinfo=timezone.utc)
    assert module.classify_publication("2026-11-23 15:21:52", now) == "STALE"
    assert module.effective_session_status("CONNECTED_ANGEL_SMARTAPI", "2026-11-23 15:21:52", now) == "STALE"


def test_recent_publication_does_not_prove_broker_session():
    now = datetime(2026, 11, 26, 8, 30, tzinfo=timezone.utc)
    assert module.classify_publication("2026-11-26 14:00:00", now) == "FRESH"
    assert module.effective_session_status("CONNECTED_ANGEL_SMARTAPI", "2026-11-26 14:00:00", now) == "RECENT_PUBLICATION_NOT_BROKER_VERIFIED"


def test_invalid_and_future_timestamps_fail_closed():
    now = datetime(2026, 11, 26, 8, 30, tzinfo=timezone.utc)
    assert module.classify_publication("", now) == "UNKNOWN"
    assert module.classify_publication("2026-11-26 14:01:00", now) == "UNKNOWN"
