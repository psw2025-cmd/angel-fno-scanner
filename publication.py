"""Explicit completion evidence for non-transactional Sheets/BQ publication.

This does not roll back writes or provide a distributed writer lease. Consumers
must use verify_current_publication before accepting combined sink output.
"""
import hashlib
import json
import uuid
import os
from datetime import datetime, timezone
from decimal import Decimal

import gspread

from sheet_grid import write_grid
from tools.ledger_writer import append_cycle
from universe_contract import require_verified_symbols
from writer_guard import ACTIVE_CYCLE, require_authorized_writer

STATUS_HEADERS = ["State", "Cycle ID", "Run ID", "Git SHA", "Writer ID",
                  "Published At (IST)", "FORENSIC_LIVE SHA256",
                  "OPTION_PREDICTIONS SHA256", "NEWS_LIVE SHA256"]
REQUIRED_TABS = ("FORENSIC_LIVE", "OPTION_PREDICTIONS", "NEWS_LIVE")


def matrix_hash(rows):
    # Sheets omits trailing blanks and returns numbers as strings.
    normalized = []
    for row in rows:
        cells = [format(Decimal(str(cell)).normalize(), "f")
                 if isinstance(cell, (int, float)) and not isinstance(cell, bool)
                 else str(cell) for cell in row]
        while cells and cells[-1] == "":
            cells.pop()
        normalized.append(cells)
    while normalized and not normalized[-1]:
        normalized.pop()
    return hashlib.sha256(json.dumps(normalized, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def sheet_symbols(title, rows):
    if title == "FORENSIC_LIVE":
        return [r[1] for r in rows[1:] if len(r) > 1 and r[1]]
    if title == "NEWS_LIVE":
        return [r[0] for r in rows[2:] if r and r[0]]
    # OPTION_PREDICTIONS includes top-N sections repeating some identities.
    start = next(i for i, r in enumerate(rows)
                 if len(r) > 2 and r[:3] == ["Rank", "Symbol", "Actionable Prediction Rating"])
    return [r[1] for r in rows[start + 1:] if len(r) > 1 and r[1]]


def verify_outputs(sh, bq_client, table_ref, identity, expected_rows=None):
    digests = []
    for title in REQUIRED_TABS:
        rows = sh.worksheet(title).get_all_values(value_render_option="UNFORMATTED_VALUE")
        require_verified_symbols(sheet_symbols(title, rows))
        digest = matrix_hash(rows)
        if expected_rows is not None and digest != matrix_hash(expected_rows[title]):
            # Metadata only: never log market values, sheet contents, or credentials.
            expected = expected_rows[title]
            first_mismatch = next(
                (i + 1 for i in range(min(len(rows), len(expected)))
                 if matrix_hash([rows[i]]) != matrix_hash([expected[i]])),
                None,
            )
            mismatch_column = None
            if first_mismatch is not None:
                actual_row = rows[first_mismatch - 1]
                expected_row = expected[first_mismatch - 1]
                mismatch_column = next(
                    (j + 1 for j in range(max(len(actual_row), len(expected_row)))
                     if matrix_hash([[actual_row[j] if j < len(actual_row) else ""]])
                     != matrix_hash([[expected_row[j] if j < len(expected_row) else ""]])),
                    None,
                )
            raise RuntimeError(
                f"{title} readback differs from this cycle's intended output "
                f"(first_mismatch_column={mismatch_column}, "
                f"actual_row_sha256={matrix_hash([rows[first_mismatch - 1]]) if first_mismatch else 'none'}, "
                f"expected_row_sha256={matrix_hash([expected[first_mismatch - 1]]) if first_mismatch else 'none'}) "
                f"(actual_rows={len(rows)}, expected_rows={len(expected)}, "
                f"first_mismatch_row={first_mismatch or 'row_count_or_trailing_cells'}, "
                f"actual_sha256={digest}, expected_sha256={matrix_hash(expected)})"
            )
        digests.append(digest)
    # Table-data read has no SQL query or scan job. Bound the read to catch extras.
    rows = list(bq_client.list_rows(table_ref, max_results=220, page_size=220))
    require_verified_symbols(row["symbol"] for row in rows)
    for row in rows:
        if any(row.get(key) != identity[key]
               for key in ("cycle_id", "run_id", "git_sha", "writer_id")):
            raise RuntimeError("BigQuery cycle/provenance readback mismatch")
        if not row.get("source_timestamp"):
            raise RuntimeError("BigQuery source timestamp absent")
    return digests


def status_worksheet(sh):
    try:
        return sh.worksheet("PUBLICATION_STATUS")
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title="PUBLICATION_STATUS", rows=2, cols=len(STATUS_HEADERS))


def verify_current_publication(sh, bq_client, table_ref):
    """Read-only check; old/missing markers and mixed output fail closed."""
    rows = sh.worksheet("PUBLICATION_STATUS").get_all_values()
    if len(rows) != 2 or rows[0] != STATUS_HEADERS or len(rows[1]) != len(STATUS_HEADERS):
        raise RuntimeError("Publication completion evidence missing or malformed")
    record = rows[1]
    if record[0] != "VERIFIED":
        raise RuntimeError(f"Publication is unverified: {record[0]}")
    identity = dict(zip(("cycle_id", "run_id", "git_sha", "writer_id"), record[1:5]))
    if any(not v or v.upper() == "UNSET" for v in identity.values()):
        raise RuntimeError("Publication identity is incomplete")
    if verify_outputs(sh, bq_client, table_ref, identity) != record[6:9]:
        raise RuntimeError("Sheets changed after completed cycle: MIXED_CYCLE")
    # Detect a competing publication while collecting evidence.
    if sh.worksheet("PUBLICATION_STATUS").get_all_values() != rows:
        raise RuntimeError("Publication changed during verification")
    return identity


def publish_outputs(sh, bq_client, table_ref, ist_str, sheet_write, bq_write):
    identity = require_authorized_writer()
    cycle_id = f"{identity['run_id']}:{uuid.uuid4().hex}"
    identity["cycle_id"] = cycle_id
    # The BigQuery transaction is authoritative. A Sheets cell is not an atomic lock.
    from tools.publication_lease import acquire_production_lease, assert_current_fence, remember_lease
    remember_lease(None)
    acquire_production_lease(client=bq_client)
    assert_current_fence(client=bq_client)
    status = status_worksheet(sh)
    token = ACTIVE_CYCLE.set(cycle_id)
    base = [cycle_id, identity["run_id"], identity["git_sha"], identity["writer_id"], ist_str]
    try:
        write_grid(status, [STATUS_HEADERS, ["PENDING", *base, "", "", ""]])
        assert_current_fence(client=bq_client)
        expected_rows = sheet_write()
        assert_current_fence(client=bq_client)
        bq_write()
        assert_current_fence(client=bq_client)
        digests = verify_outputs(sh, bq_client, table_ref, identity, expected_rows)
        # BQ freshness indicator is advanced only after actual successful readback.
        hb = sh.worksheet("HEARTBEAT")
        headers = hb.row_values(1)
        if "Last BigQuery Sync (IST)" in headers:
            from gspread.utils import rowcol_to_a1
            hb.update(range_name=rowcol_to_a1(2, headers.index("Last BigQuery Sync (IST)") + 1),
                      values=[[ist_str]], value_input_option="RAW")
        sh.worksheet("OPTION_PREDICTIONS").update(
            range_name="G2", values=[["Publication: VERIFIED_READBACK"]], value_input_option="RAW")
        expected_rows["OPTION_PREDICTIONS"][1][6] = "Publication: VERIFIED_READBACK"
        # The G2 status change is part of the final matrix digest.
        digests = verify_outputs(sh, bq_client, table_ref, identity, expected_rows)
        assert_current_fence(client=bq_client)
        write_grid(status, [STATUS_HEADERS, ["VERIFIED", *base, *digests]])
        verify_current_publication(sh, bq_client, table_ref)
        # The ledger is local evidence only; publication readback remains authoritative.
        ledger_path = os.environ.get('ANGEL_CYCLE_LEDGER_PATH')
        if ledger_path:
            append_cycle(ledger_path, {
                'ts': datetime.now(timezone.utc).isoformat(),
                'cycle_id': cycle_id, 'run_id': identity['run_id'],
                'git_sha': identity['git_sha'], 'status': 'VERIFIED',
            })
        return identity
    except Exception:
        try:
            write_grid(status, [STATUS_HEADERS, ["FAILED_PARTIAL", *base, "", "", ""]])
        except Exception:
            # PENDING or the readback mismatch still prevents a verified verdict.
            pass
        raise
    finally:
        ACTIVE_CYCLE.reset(token)
        remember_lease(None)
