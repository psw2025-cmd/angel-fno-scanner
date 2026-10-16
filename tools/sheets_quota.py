"""Bounded retry for Google Sheets 429 (read/write quota) errors.

`install()` wraps gspread's HTTP client once so every caller (scanner,
prediction engine, writer_guard) tolerates transient per-minute quota limits.
Only HTTP 429 is retried; every other error propagates unchanged and a
persistent 429 still raises (fail closed).
"""
from __future__ import annotations

import functools
import time

RETRY_DELAYS = (5, 10, 20, 40, 60)
_sleep = time.sleep
_INSTALLED_FLAG = "_angel_quota_retry_installed"


def is_quota_error(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        return status == 429
    text = str(exc)
    return "[429]" in text or "Quota exceeded" in text


def with_retry(fn, delays=None):
    """Wrap ``fn`` so 429 errors are retried with bounded backoff."""
    schedule = RETRY_DELAYS if delays is None else delays

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for delay in schedule:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                if not is_quota_error(exc):
                    raise
                _sleep(delay)
        return fn(*args, **kwargs)

    setattr(wrapper, _INSTALLED_FLAG, True)
    return wrapper


def install() -> bool:
    """Idempotently wrap gspread HTTPClient.request. Returns True if newly installed."""
    from gspread import http_client

    current = http_client.HTTPClient.request
    if getattr(current, _INSTALLED_FLAG, False):
        return False
    http_client.HTTPClient.request = with_retry(current)
    return True
