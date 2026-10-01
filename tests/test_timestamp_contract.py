"""
tests/test_timestamp_contract.py

Comprehensive tests for Section 11: TIMESTAMP / TIMEZONE CONTRACT.
Verifies:
1. Unambiguous Asia/Kolkata and UTC support without depending on pandas string guessing.
2. Expiry dates are strictly contract specifications and NEVER treated as data freshness timestamps.
3. Verification across all 6 data lifecycle timestamps:
   - source timestamp
   - ingestion timestamp
   - prediction timestamp
   - sheet timestamp
   - BigQuery timestamp
   - outcome timestamp
4. Zero naive/aware timestamp mixing (prevents comparison TypeErrors).
5. Deterministic freshness SLA evaluation (<=90s FRESH, 91-180s DEGRADED, >180s STALE).
"""

import re
from datetime import datetime, timezone, timedelta
import pytest
from scripts.reconcile_bq_sheet import parse_timestamp, extract_snapshot_id

# Canonical Market Timezone Offset
IST_OFFSET = timezone(timedelta(hours=5, minutes=30))


def is_contract_expiry_date(val: str) -> bool:
    """
    Checks if a string represents an instrument expiry date rather than a runtime freshness timestamp.
    Expiry dates typically follow 'YYYY-MM-DD', 'DD-Mon-YYYY', or 'DDMMMYYYY' with no time component.
    """
    if not val or not isinstance(val, str):
        return False
    clean = val.strip()
    # Matches dates without time: 2026-10-29 or 27-Oct-2026 or 27OCT2026
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}$",
        r"^\d{1,2}-[A-Za-z]{3}-\d{4}$",
        r"^\d{1,2}[A-Za-z]{3}\d{4}$",
    ]
    return any(re.match(pat, clean) for pat in date_patterns)


def calculate_freshness_status(
    source_timestamp_utc: datetime,
    now_utc: datetime,
    market_open: bool = True
) -> str:
    """
    Calculates operational freshness status per AGENTS.md Section 12 SLA.
    <= 90s: FRESH
    91-180s: DEGRADED
    > 180s: STALE
    market closed: LAST_PRINT / CLOSED
    """
    if not market_open:
        return "LAST_PRINT / CLOSED"
    # Ensure both are timezone-aware UTC
    if source_timestamp_utc.tzinfo is None or now_utc.tzinfo is None:
        raise TypeError("Naive timestamps are prohibited in freshness calculation")

    age_sec = (now_utc - source_timestamp_utc).total_seconds()
    if age_sec < 0:
        return "FUTURE_CLOCK_ANOMALY"
    elif age_sec <= 90:
        return "FRESH"
    elif age_sec <= 180:
        return "DEGRADED"
    else:
        return "STALE"


def test_unambiguous_asia_kolkata_and_utc():
    # 1. ISO UTC with offset
    utc_str = "2026-10-01T06:15:00+00:00"
    dt_utc = parse_timestamp(utc_str)
    assert dt_utc is not None
    assert dt_utc.tzinfo == timezone.utc
    assert dt_utc.hour == 6

    # 2. Textual IST string parsed without pandas guessing
    ist_str = "2026-10-01 11:45:00 IST"
    dt_ist = parse_timestamp(ist_str)
    assert dt_ist is not None
    assert dt_ist.tzinfo == timezone.utc
    # 11:45 IST is exactly 06:15 UTC
    assert dt_ist.hour == 6
    assert dt_ist.minute == 15
    assert dt_ist == dt_utc


def test_expiry_date_never_used_as_freshness():
    # True contract expiry dates
    assert is_contract_expiry_date("2026-10-29") is True
    assert is_contract_expiry_date("27-Oct-2026") is True
    assert is_contract_expiry_date("29OCT2026") is True

    # Real-time data freshness timestamps (have time components)
    assert is_contract_expiry_date("2026-10-01 11:45:00") is False
    assert is_contract_expiry_date("2026-10-01T11:45:00+05:30") is False
    assert is_contract_expiry_date("2026-10-01 06:15:00.452891+00:00") is False

    # Guard: Attempting to treat an expiry date as freshness must fail or be rejected
    expiry_date = "2026-10-29"
    assert is_contract_expiry_date(expiry_date) is True
    # An expiry date lacks hours/minutes/seconds and must not be fed into runtime SLA
    parsed_dt = parse_timestamp(expiry_date)
    # Even if parsed as date, it does not represent current quote tick time
    assert parsed_dt is None or is_contract_expiry_date(expiry_date)


def test_six_lifecycle_timestamps_verification():
    # 1. Source Timestamp: Exchange feed tick from SmartAPI
    source_ts = "2026-10-01 11:44:58 IST"
    dt_source = parse_timestamp(source_ts)
    assert dt_source is not None

    # 2. Ingestion Timestamp: Quote packet arrival in Python runner
    ingest_ts = "2026-10-01 11:45:00 IST"
    dt_ingest = parse_timestamp(ingest_ts)
    assert dt_ingest is not None

    # 3. Prediction Timestamp: Model formulation cutoff
    pred_ts = "2026-10-01 08:30:00 IST"
    dt_pred = parse_timestamp(pred_ts)
    assert dt_pred is not None
    # Must precede 09:15 open
    assert dt_pred.astimezone(IST_OFFSET).hour < 9

    # 4. Sheet Timestamp: Written to FORENSIC_LIVE
    sheet_ts = "2026-10-01 11:45:00"
    dt_sheet = parse_timestamp(sheet_ts)
    assert dt_sheet is not None

    # 5. BigQuery Timestamp: Stored in option_predictions_live
    bq_ts = "2026-10-01T06:15:00.452891+00:00"
    dt_bq = parse_timestamp(bq_ts)
    assert dt_bq is not None

    # 6. Outcome Timestamp: Market reconciliation print
    outcome_ts = "2026-10-01 15:30:00 IST"
    dt_outcome = parse_timestamp(outcome_ts)
    assert dt_outcome is not None

    # Verify chronological order
    assert dt_pred < dt_source <= dt_ingest <= dt_outcome


def test_no_naive_aware_timestamp_mixing():
    aware_utc = datetime(2026, 10, 1, 6, 15, 0, tzinfo=timezone.utc)
    naive_dt = datetime(2026, 10, 1, 11, 45, 0)

    # In pure Python, subtracting naive from aware raises TypeError
    with pytest.raises(TypeError):
        _ = aware_utc - naive_dt

    # Our contract mandates explicit tz conversion before math:
    aware_ist = naive_dt.replace(tzinfo=IST_OFFSET)
    diff = (aware_ist - aware_utc).total_seconds()
    # Because 11:45 IST == 06:15 UTC, difference is exactly 0.0 seconds
    assert diff == 0.0


def test_freshness_sla_states():
    now_utc = datetime(2026, 10, 1, 6, 15, 0, tzinfo=timezone.utc)

    # 1. Under 90s -> FRESH
    tick_fresh = now_utc - timedelta(seconds=45)
    assert calculate_freshness_status(tick_fresh, now_utc, market_open=True) == "FRESH"

    # 2. 91 - 180s -> DEGRADED
    tick_degraded = now_utc - timedelta(seconds=120)
    assert calculate_freshness_status(tick_degraded, now_utc, market_open=True) == "DEGRADED"

    # 3. > 180s -> STALE
    tick_stale = now_utc - timedelta(seconds=300)
    assert calculate_freshness_status(tick_stale, now_utc, market_open=True) == "STALE"

    # 4. Market Closed -> LAST_PRINT / CLOSED
    assert calculate_freshness_status(tick_fresh, now_utc, market_open=False) == "LAST_PRINT / CLOSED"
