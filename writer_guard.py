"""Single-writer guard and provenance helpers for production sinks."""
import datetime
import os
import time
from contextvars import ContextVar
from zoneinfo import ZoneInfo

AUTHORIZED_WRITER_ID = "market_bot"
IST = ZoneInfo("Asia/Kolkata")
ACTIVE_CYCLE = ContextVar("publication_cycle", default=None)


def build_provenance(source_timestamp=None):
    if source_timestamp is None:
        source_timestamp = datetime.datetime.now(IST).replace(microsecond=0).isoformat()
    try:
        from tools.cycle_provenance import resolve_git_sha, resolve_run_id
        run_id = resolve_run_id()
        git_sha = resolve_git_sha()
    except Exception:
        run_id = "UNSET"
        git_sha = "UNSET"
    result = {
        "run_id": run_id,
        "git_sha": git_sha,
        "writer_id": (os.getenv("WRITER_ID") or "UNSET").strip(),
        "source_timestamp": str(source_timestamp),
    }
    if ACTIVE_CYCLE.get():
        result["cycle_id"] = ACTIVE_CYCLE.get()
    return result


def require_authorized_writer():
    provenance = build_provenance()
    enabled = (os.getenv("ALLOW_PRODUCTION_WRITES") or "0").strip() == "1"
    if not enabled or provenance["writer_id"] != AUTHORIZED_WRITER_ID:
        raise RuntimeError(
            "Production sink write blocked: only market_bot with "
            "ALLOW_PRODUCTION_WRITES=1 is authorized."
        )
    if any(not provenance[field] or provenance[field].upper() == "UNSET"
           for field in ("run_id", "git_sha")):
        raise RuntimeError("Production sink write blocked: run_id and git_sha are required")
    return provenance


def append_sheet_provenance(sh, sink, record_count, source_timestamp):
    """Append one trace row for a Sheet write event without changing sink schemas."""
    provenance = require_authorized_writer()
    provenance = build_provenance(source_timestamp)
    headers = [
        "Source Timestamp",
        "Run ID",
        "Git SHA",
        "Writer ID",
        "Sink",
        "Record Count",
    ]
    ws = _get_or_create_provenance_sheet(sh)
    header_row = _with_quota_retry(lambda: ws.row_values(1))
    if header_row != headers:
        _with_quota_retry(lambda: ws.update(range_name="A1", values=[headers], value_input_option="RAW"))
    _with_quota_retry(lambda: ws.append_row(
        [
            provenance["source_timestamp"],
            provenance["run_id"],
            provenance["git_sha"],
            provenance["writer_id"],
            str(sink),
            int(record_count),
        ],
        value_input_option="RAW",
    ))
    return provenance


QUOTA_RETRY_DELAYS = (5, 15, 30, 60)
_sleep = time.sleep


def _is_quota_error(exc):
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    text = str(exc)
    return "[429]" in text or "Quota exceeded" in text


def _with_quota_retry(fn):
    """Retry only Sheets quota (429) errors, bounded; everything else propagates."""
    for delay in QUOTA_RETRY_DELAYS:
        try:
            return fn()
        except Exception as exc:
            if not _is_quota_error(exc):
                raise
            _sleep(delay)
    return fn()


def _get_or_create_provenance_sheet(sh):
    """Create WRITE_PROVENANCE only when it is genuinely missing.

    A transient API error (for example a 429 on a read) must never be treated
    as "sheet missing"; that previously crashed the cycle with an
    "already exists" error from add_worksheet.
    """
    import gspread

    title = "WRITE_PROVENANCE"
    try:
        return _with_quota_retry(lambda: sh.worksheet(title))
    except gspread.exceptions.WorksheetNotFound:
        pass
    try:
        return _with_quota_retry(lambda: sh.add_worksheet(title=title, rows="2000", cols="6"))
    except gspread.exceptions.APIError as exc:
        if "already exists" not in str(exc):
            raise
        return _with_quota_retry(lambda: sh.worksheet(title))
