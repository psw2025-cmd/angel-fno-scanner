"""Atomic paper-cycle lease shared by GitHub Actions and Cloud Run.

BigQuery serializes mutating DML on ``transaction_write_lock``. The owner id
embeds a monotonic fencing token. A writer whose token is no longer current
cannot renew and must not publish. Live broker orders are refused.
"""
from __future__ import annotations

import datetime
import os
import re
from zoneinfo import ZoneInfo

from google.cloud import bigquery

IST = ZoneInfo("Asia/Kolkata")
LIVE_ORDER_FLAGS = (
    "ALLOW_LIVE_BROKER_ORDERS",
    "PLACE_REAL_ORDERS",
    "ANGEL_LIVE_ORDERS",
)
_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,127}$")
_LOCK_KEY = re.compile(r"^paper-cycle:\d{4}-\d{2}-\d{2}:(OPEN|CLOSED|EOD)$")
_CURRENT: dict | None = None


class PublicationLeaseError(RuntimeError):
    pass


def assert_paper_publisher() -> None:
    for flag in LIVE_ORDER_FLAGS:
        if (os.getenv(flag) or "0").strip() == "1":
            raise PublicationLeaseError(
                f"paper publisher refused live-order flag {flag}"
            )
    if (os.getenv("LIVE_ORDER_AUTHORITY") or "").strip() == "1":
        raise PublicationLeaseError(
            "paper publisher refused LIVE_ORDER_AUTHORITY=1"
        )
    if (os.getenv("PAPER_MODE") or "").strip() == "0":
        raise PublicationLeaseError(
            "paper publisher refused PAPER_MODE=0"
        )


def cycle_lock_key(now: datetime.datetime | None = None) -> str:
    moment = now or datetime.datetime.now(IST)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=IST)
    session = (os.getenv("ANGEL_MARKET_SESSION") or "EOD").strip().upper()
    if session not in {"OPEN", "CLOSED", "EOD"}:
        raise PublicationLeaseError(f"invalid publication session {session!r}")
    key = f"paper-cycle:{moment.astimezone(IST):%Y-%m-%d}:{session}"
    if not _LOCK_KEY.fullmatch(key):
        raise PublicationLeaseError("invalid paper-cycle lock key")
    return key


def parse_owner(owner_id: str | None) -> tuple[int, str, str]:
    parts = (owner_id or "").split("|")
    if len(parts) != 3:
        return 0, "", ""
    try:
        token = int(parts[0])
    except ValueError:
        return 0, "", ""
    if token < 1:
        return 0, "", ""
    return token, parts[1], parts[2]


def format_owner(token: int, writer_id: str, execution_id: str) -> str:
    if token < 1 or not writer_id or not execution_id or "|" in writer_id or "|" in execution_id:
        raise PublicationLeaseError("invalid fencing owner")
    return f"{token}|{writer_id}|{execution_id}"


def decide_lease(
    existing: dict | None,
    *,
    writer_id: str,
    execution_id: str,
    now: datetime.datetime,
    lease_seconds: int,
) -> dict:
    """Pure acquire decision. ``existing`` is the current lock row or None."""
    assert_paper_publisher()
    if lease_seconds < 30:
        raise PublicationLeaseError("lease must be at least 30 seconds")
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    if not existing:
        owner = format_owner(1, writer_id, execution_id)
        return {"action": "insert", "owner_id": owner, "fencing_token": 1, "publish": True}
    owner_id = str(existing.get("owner_id") or "")
    token, owner_writer, owner_exec = parse_owner(owner_id)
    acquired = existing.get("acquired_at")
    duration = int(existing.get("lease_duration_sec") or 0)
    if not isinstance(acquired, datetime.datetime):
        expired = True
    else:
        if acquired.tzinfo is None:
            acquired = acquired.replace(tzinfo=datetime.timezone.utc)
        expired = acquired + datetime.timedelta(seconds=duration) < now
    same_holder = owner_writer == writer_id and owner_exec == execution_id and token >= 1
    if same_holder and not expired:
        return {
            "action": "renew",
            "owner_id": owner_id,
            "fencing_token": token,
            "publish": True,
        }
    if expired or token < 1:
        new_token = token + 1 if token >= 1 else 1
        owner = format_owner(new_token, writer_id, execution_id)
        return {"action": "fence", "owner_id": owner, "fencing_token": new_token, "publish": True}
    return {
        "action": "blocked",
        "owner_id": owner_id,
        "fencing_token": token,
        "publish": False,
    }


def _qualified_table() -> str:
    project = (os.getenv("BQ_PROJECT_ID") or "fno-angel-prod-1790444589").strip()
    dataset = (os.getenv("BQ_DATASET_ID") or os.getenv("BQ_DATASET") or "fno_predictions").strip()
    table = "transaction_write_lock"
    for label, ident in (("project", project), ("dataset", dataset), ("table", table)):
        if not _IDENT.fullmatch(ident):
            raise PublicationLeaseError(f"unsafe BigQuery {label} identifier")
    return f"`{project}.{dataset}.{table}`"


def _script(decision_sql: str) -> str:
    table = _qualified_table()
    return f"""
DECLARE existing_owner STRING;
DECLARE existing_acquired TIMESTAMP;
DECLARE existing_lease INT64;
DECLARE existing_token INT64 DEFAULT 0;
DECLARE is_expired BOOL DEFAULT TRUE;
DECLARE new_token INT64;
DECLARE new_owner STRING;
DECLARE decision STRING DEFAULT 'blocked';

BEGIN TRANSACTION;

SET (existing_owner, existing_acquired, existing_lease) = (
  SELECT AS STRUCT owner_id, acquired_at, lease_duration_sec
  FROM {table}
  WHERE lock_key = @lock_key
);

IF existing_owner IS NULL THEN
  SET new_token = 1;
  SET new_owner = CONCAT(CAST(new_token AS STRING), '|', @writer_id, '|', @execution_id);
  INSERT INTO {table} (lock_key, acquired_at, owner_id, lease_duration_sec)
  VALUES (@lock_key, CURRENT_TIMESTAMP(), new_owner, @lease_seconds);
  SET decision = 'insert';
ELSE
  SET existing_token = IFNULL(SAFE_CAST(SPLIT(existing_owner, '|')[SAFE_OFFSET(0)] AS INT64), 0);
  SET is_expired = TIMESTAMP_ADD(existing_acquired, INTERVAL existing_lease SECOND) < CURRENT_TIMESTAMP();
  IF existing_token >= 1
     AND existing_owner = CONCAT(CAST(existing_token AS STRING), '|', @writer_id, '|', @execution_id)
     AND NOT is_expired THEN
    UPDATE {table}
    SET acquired_at = CURRENT_TIMESTAMP(), lease_duration_sec = @lease_seconds
    WHERE lock_key = @lock_key AND owner_id = existing_owner;
    SET new_token = existing_token;
    SET new_owner = existing_owner;
    SET decision = 'renew';
  ELSEIF is_expired OR existing_token < 1 THEN
    SET new_token = IF(existing_token >= 1, existing_token + 1, 1);
    SET new_owner = CONCAT(CAST(new_token AS STRING), '|', @writer_id, '|', @execution_id);
    UPDATE {table}
    SET owner_id = new_owner,
        acquired_at = CURRENT_TIMESTAMP(),
        lease_duration_sec = @lease_seconds
    WHERE lock_key = @lock_key AND owner_id = existing_owner;
    IF (SELECT owner_id FROM {table} WHERE lock_key = @lock_key) = new_owner THEN
      SET decision = 'fence';
    ELSE
      SET decision = 'blocked';
      SET new_owner = existing_owner;
      SET new_token = existing_token;
    END IF;
  ELSE
    SET decision = 'blocked';
    SET new_owner = existing_owner;
    SET new_token = existing_token;
  END IF;
END IF;

COMMIT TRANSACTION;

SELECT decision, new_owner AS owner_id, new_token AS fencing_token;
""".strip()


def lease_script() -> str:
    """SQL used for the atomic acquire. Exposed for the regression test."""
    return _script("")


def _query_params(lock_key: str, writer_id: str, execution_id: str, lease_seconds: int):
    return [
        bigquery.ScalarQueryParameter("lock_key", "STRING", lock_key),
        bigquery.ScalarQueryParameter("writer_id", "STRING", writer_id),
        bigquery.ScalarQueryParameter("execution_id", "STRING", execution_id),
        bigquery.ScalarQueryParameter("lease_seconds", "INT64", lease_seconds),
    ]


def _client():
    project = (os.getenv("BQ_PROJECT_ID") or "fno-angel-prod-1790444589").strip()
    return bigquery.Client(project=project)


def remember_lease(lease: dict | None) -> None:
    global _CURRENT
    _CURRENT = lease


def current_lease() -> dict | None:
    return _CURRENT


def acquire_production_lease(client=None, *, now: datetime.datetime | None = None) -> dict:
    """Take the paper-cycle lease or fail closed. Does not place broker orders."""
    assert_paper_publisher()
    if (os.getenv("ALLOW_PRODUCTION_WRITES") or "0").strip() != "1":
        raise PublicationLeaseError(
            "publication lease refused because ALLOW_PRODUCTION_WRITES is not 1"
        )
    from tools.cycle_provenance import resolve_git_sha, resolve_run_id

    run_id = resolve_run_id()
    git_sha = resolve_git_sha()
    writer_id = (os.getenv("WRITER_ID") or "").strip()
    if writer_id != "market_bot":
        raise PublicationLeaseError("publication lease requires WRITER_ID=market_bot")
    lock_key = cycle_lock_key(now)
    lease_seconds = int(os.getenv("PUBLICATION_LEASE_SECONDS") or "900")
    job = bigquery.QueryJobConfig(query_parameters=_query_params(
        lock_key, writer_id, run_id, lease_seconds
    ))
    bq = client or _client()
    rows = list(bq.query(lease_script(), job_config=job).result())
    if len(rows) != 1:
        raise PublicationLeaseError("publication lease script did not return one decision")
    decision = str(rows[0]["decision"])
    owner_id = str(rows[0]["owner_id"])
    token = int(rows[0]["fencing_token"])
    if decision not in {"insert", "renew", "fence"}:
        raise PublicationLeaseError(
            f"publication lease held by another writer for {lock_key}; this cycle will not publish"
        )
    lease = {
        "action": decision,
        "lock_key": lock_key,
        "owner_id": owner_id,
        "fencing_token": token,
        "run_id": run_id,
        "git_sha": git_sha,
        "writer_id": writer_id,
    }
    remember_lease(lease)
    return lease


def assert_current_fence(client=None) -> dict:
    """Renew only if this process still holds the unexpired fencing token."""
    lease = current_lease()
    if not lease:
        raise PublicationLeaseError("stale writer has no publication lease")
    assert_paper_publisher()
    table = _qualified_table()
    script = f"""
DECLARE still INT64 DEFAULT 0;
BEGIN TRANSACTION;
UPDATE {table}
SET acquired_at = CURRENT_TIMESTAMP()
WHERE lock_key = @lock_key
  AND owner_id = @owner_id
  AND TIMESTAMP_ADD(acquired_at, INTERVAL lease_duration_sec SECOND) >= CURRENT_TIMESTAMP();
SET still = (
  SELECT COUNT(*)
  FROM {table}
  WHERE lock_key = @lock_key
    AND owner_id = @owner_id
    AND TIMESTAMP_ADD(acquired_at, INTERVAL lease_duration_sec SECOND) >= CURRENT_TIMESTAMP()
);
COMMIT TRANSACTION;
SELECT still AS still_held;
""".strip()
    job = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("lock_key", "STRING", lease["lock_key"]),
        bigquery.ScalarQueryParameter("owner_id", "STRING", lease["owner_id"]),
    ])
    bq = client or _client()
    try:
        rows = list(bq.query(script, job_config=job).result())
    except Exception as exc:
        raise PublicationLeaseError("stale writer lost the publication fence") from exc
    if not rows or int(rows[0]["still_held"]) != 1:
        raise PublicationLeaseError("stale writer lost the publication fence")
    return lease
