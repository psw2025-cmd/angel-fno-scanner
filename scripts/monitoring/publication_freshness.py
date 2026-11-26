"""Fail-closed freshness classification for Angel workbook timestamps.

Pure, dependency-free utility. No broker connection or sheet writes.
Never equate a stored CONNECTED string with a current live session.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def classify_publication(timestamp_ist: str, now_utc: datetime, max_age_minutes: int = 15) -> str:
    """Return FRESH, STALE or UNKNOWN; fail closed on missing/invalid/future timestamps."""
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone aware")
    if max_age_minutes <= 0:
        raise ValueError("max_age_minutes must be positive")
    try:
        issued = datetime.strptime(timestamp_ist.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    except (AttributeError, ValueError):
        return "UNKNOWN"
    age = now_utc.astimezone(timezone.utc) - issued.astimezone(timezone.utc)
    if age < timedelta(0):
        return "UNKNOWN"
    return "FRESH" if age <= timedelta(minutes=max_age_minutes) else "STALE"


def effective_session_status(stored_status: str, timestamp_ist: str, now_utc: datetime) -> str:
    """A historical CONNECTED string is not proof of a current broker session."""
    freshness = classify_publication(timestamp_ist, now_utc)
    if freshness != "FRESH":
        return freshness
    return "RECENT_PUBLICATION_NOT_BROKER_VERIFIED"
