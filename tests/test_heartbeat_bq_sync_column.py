"""HEARTBEAT C2 must not retain non-timestamp values such as row counts."""
import datetime


def sanitize_bq_sync_cell(prev):
    """Mirror scanner HEARTBEAT guard for Last BigQuery Sync (IST)."""
    prev = str(prev).strip() if prev is not None else ""
    if not prev:
        return ""
    try:
        datetime.datetime.strptime(prev[:19], "%Y-%m-%d %H:%M:%S")
        return prev
    except Exception:
        return ""


def test_rejects_row_count_in_bq_sync_column():
    assert sanitize_bq_sync_cell("219") == ""
    assert sanitize_bq_sync_cell(219) == ""
    assert sanitize_bq_sync_cell("2026-10-03 14:32:50") == "2026-10-03 14:32:50"
    assert sanitize_bq_sync_cell("") == ""


def test_universe_contract_is_219():
    from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT
    assert EXPECTED_FNO_UNIVERSE_COUNT == 219
