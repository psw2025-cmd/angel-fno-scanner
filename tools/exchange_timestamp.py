"""Parse quote-supplied exchange time, never processing time."""
from datetime import datetime, timezone

def get_exchange_timestamp(raw_data):
    if not isinstance(raw_data, dict):
        raise ValueError("quote must be an object")
    # Angel FULL quote API provides exchange timestamp in exchFeedTime.
    raw = raw_data.get("exchFeedTime")
    if raw is None or str(raw).strip() == "":
        raise ValueError("quote missing exchFeedTime; source freshness unverified")
    if isinstance(raw, (int, float)):
        if raw <= 0:
            raise ValueError("invalid exchange epoch")
        value = datetime.fromtimestamp(raw, timezone.utc)
    else:
        text = str(raw).strip()
        if text.isdigit():
            value = datetime.fromtimestamp(int(text), timezone.utc)
        else:
            try:
                value = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                # Angel SmartAPI FULL quote's documented exchange-local format.
                from zoneinfo import ZoneInfo
                value = datetime.strptime(text, "%d-%b-%Y %H:%M:%S").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
            if value.tzinfo is None:
                raise ValueError("exchange time missing timezone")
    return value.astimezone(timezone.utc).isoformat()


def oldest_exchange_timestamp(quotes):
    """Oldest quote tick across the complete supplied universe; reject any missing."""
    from datetime import datetime
    quotes = list(quotes)
    if not quotes:
        raise ValueError("no quotes available to verify")
    return min(datetime.fromisoformat(get_exchange_timestamp(q)) for q in quotes).isoformat()
