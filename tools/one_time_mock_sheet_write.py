#!/usr/bin/env python3
"""Write ONE readback-verified synthetic replay receipt to its isolated workbook tab.

Never marks real PUBLICATION_STATUS or OPTION_PREDICTIONS as successful/active.
A synthetic replay cannot satisfy the real market/exchange/BigQuery proof gates.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from credentials import load_service_account, require_authoritative_sheet_id
from tools.mock_replay import build_replay

TARGET_TAB = "MOCK_REPLAY_EVIDENCE"
CANONICAL_SHEET_ID = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
PROTECTED_TABS = ("PUBLICATION_STATUS", "OPTION_PREDICTIONS", "FORENSIC_LIVE", "WRITE_PROVENANCE")


def digest(rows):
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


def evidence_rows(payload):
    if (payload.get("mode") != "MOCK_REPLAY" or
            payload.get("live_verified") is not False or
            payload.get("broker_calls") != 0 or
            payload.get("real_orders") != 0 or
            payload.get("sink_writes") != 0 or
            payload.get("underlyings") != 219 or
            payload.get("ranked_ce_pe_contracts") != 200 or
            not payload.get("stale_negative_control_rejected")):
        raise RuntimeError("Invalid simulation: refused synthetic workbook write")
    return [
        ["Field", "Value"],
        ["DATA_CLASS", "SYNTHETIC / MOCK_REPLAY / NOT LIVE"],
        ["MOCK_PUBLICATION_STATUS", "SUCCESS_MOCK_REPLAY_ONLY"],
        ["MOCK_OPTION_PREDICTIONS_STATUS", "VERIFIED_ACTIVE_MOCK_ONLY"],
        ["EXCHANGE_SOURCE", "SIMULATED; NO BROKER TICKS"],
        ["PRODUCTION_PUBLICATION_STATUS", "UNMODIFIED; SEE PUBLICATION_STATUS!A2"],
        ["PRODUCTION_OPTION_STATUS", "UNMODIFIED; SEE OPTION_PREDICTIONS!G2"],
        ["REPLAY_RUN_ID", payload["run_id"]],
        ["EXACT_GIT_SHA", payload["git_sha"]],
        ["SIMULATED_CYCLE_ID", payload["cycle_id"]],
        ["GENERATED_AT_UTC", payload["generated_at_utc"]],
        ["CANONICAL_UNDERLYINGS_SIMULATED", str(payload["underlyings"])],
        ["SIMULATED_CE_PE_CONTRACTS", str(payload["ranked_ce_pe_contracts"])],
        ["SYNTHETIC_PAPER_LIFECYCLE", " -> ".join(payload["paper_lifecycle"])],
        ["STALE_TICK_NEGATIVE_CONTROL", "PASS" if payload["stale_negative_control_rejected"] else "FAIL"],
        ["BROKER_API_CALLS", "0"],
        ["REAL_BROKER_ORDERS", "0"],
        ["PRODUCTION_DATA_SINK_WRITES", "0"],
        ["MOCK_REPLAY_PAYLOAD_SHA256", payload["sha256"]],
    ]


def verify_locks():
    for k, expected in (("PAPER_MODE", "1"),
                        ("LIVE_ORDER_AUTHORITY", "0"),
                        ("REAL_BROKER_ORDERS", "0"),
                        ("ALLOW_PRODUCTION_WRITES", "0")):
        if os.environ.get(k, expected) != expected:
            raise RuntimeError(f"Unsafe environment lock for MOCK_REPLAY: {k}")


def execute(book, payload):
    verify_locks()
    intended = evidence_rows(payload)
    tabs = book.worksheets()
    canonical = [w for w in tabs if w.title != TARGET_TAB]
    if len(canonical) != 30:
        raise RuntimeError(f"Canonical workbook tab drift: expected 30, found {len(canonical)}")
    protected_before = {name: digest(book.worksheet(name).get_all_values()) for name in PROTECTED_TABS}
    prod_state_before = book.worksheet("PUBLICATION_STATUS").acell("A2").value
    prod_option_before = book.worksheet("OPTION_PREDICTIONS").acell("G2").value
    try:
        ws = book.worksheet(TARGET_TAB)
        if ws.get("A1:B2") and ws.acell("A1").value not in (None, "", "Field"):
            raise RuntimeError("Existing target tab is not a mock-evidence tab")
    except Exception as exc:
        if exc.__class__.__name__ != "WorksheetNotFound":
            raise
        ws = book.add_worksheet(title=TARGET_TAB, rows=40, cols=2)
    # A sole isolated tab update, never the production publisher or option feed.
    ws.update(range_name=f"A1:B{len(intended)}", values=intended, value_input_option="RAW")
    readback = ws.get(f"A1:B{len(intended)}", value_render_option="FORMATTED_VALUE")
    if readback != intended:
        raise RuntimeError(f"MOCK_EVIDENCE_READBACK_MISMATCH expected={digest(intended)} actual={digest(readback)}")
    protected_after = {name: digest(book.worksheet(name).get_all_values()) for name in PROTECTED_TABS}
    if protected_before != protected_after:
        raise RuntimeError("PRODUCTION_TAB_CHANGED_DURING_MOCK_WRITE")
    prod_state_after = book.worksheet("PUBLICATION_STATUS").acell("A2").value
    prod_option_after = book.worksheet("OPTION_PREDICTIONS").acell("G2").value
    if (prod_state_after != prod_state_before or prod_option_after != prod_option_before):
        raise RuntimeError("Production status overwritten during mock evidence write")
    print(f"MOCK_SHEET_WRITE_EXIT_0 sheet_tab={TARGET_TAB} cell_range=A1:B{len(intended)}")
    for key, value in intended[1:]:
        print(f"READBACK_VERIFIED {key}={value}")
    print(f"READBACK_MATRIX_SHA256={digest(readback)}")
    print(f"PRODUCTION_PUBLICATION_STATUS_UNCHANGED={prod_state_after}")
    print(f"PRODUCTION_OPTION_STATUS_UNCHANGED={prod_option_after}")
    print("MOCK_TEST_SUCCESS=YES; LIVE_PUBLICATION_CERTIFIED=NO; REAL_BROKER_ORDERS=0")
    return readback


def main():
    verify_locks()
    actual=require_authoritative_sheet_id(os.environ.get("SHEET_ID", ""))
    if actual != CANONICAL_SHEET_ID:
        raise RuntimeError("Refusing to write an unapproved workbook")
    import gspread
    book = gspread.service_account_from_dict(load_service_account()).open_by_key(actual)
    payload = build_replay()
    execute(book, payload)
    # Files used only in runner evidence; no secrets or raw market records.
    out = Path("proof-output/mock_sheet_write_receipt.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"mode": "MOCK_REPLAY_ONLY", "git_sha": payload["git_sha"],
                               "run_id": payload["run_id"], "source_sha256": payload["sha256"],
                               "target_tab": TARGET_TAB, "status": "SUCCESS_MOCK_REPLAY_ONLY"},
                              sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("MOCK_RECEIPT_JSON_VERIFIED=" + str(out))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MOCK_SHEET_WRITE_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
