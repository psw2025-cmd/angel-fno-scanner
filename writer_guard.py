"""Single-writer guard and provenance helpers for production sinks."""
import datetime
import os
from contextvars import ContextVar
from zoneinfo import ZoneInfo

AUTHORIZED_WRITER_ID = "market_bot"
IST = ZoneInfo("Asia/Kolkata")
ACTIVE_CYCLE = ContextVar("publication_cycle", default=None)


def build_provenance(source_timestamp=None):
    if source_timestamp is None:
        source_timestamp = datetime.datetime.now(IST).replace(microsecond=0).isoformat()
    result = {
        "run_id": (os.getenv("RUN_ID") or os.getenv("GITHUB_RUN_ID") or "UNSET").strip(),
        "git_sha": (os.getenv("GIT_SHA") or os.getenv("GITHUB_SHA") or "UNSET").strip(),
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
    try:
        ws = sh.worksheet("WRITE_PROVENANCE")
    except Exception:
        ws = sh.add_worksheet(title="WRITE_PROVENANCE", rows="2000", cols="6")
    if ws.row_values(1) != headers:
        ws.update(range_name="A1", values=[headers], value_input_option="RAW")
    ws.append_row(
        [
            provenance["source_timestamp"],
            provenance["run_id"],
            provenance["git_sha"],
            provenance["writer_id"],
            str(sink),
            int(record_count),
        ],
        value_input_option="RAW",
    )
    return provenance
