#!/usr/bin/env python3
"""Direct service-account Google Sheet forensic audit and nine-cell fail-closed repair.

Does not use Autosheet. Does not submit real broker orders, modify provenance,
rewrite market data, or confuse a readback with a live-market certification.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter

from credentials import load_service_account, require_authoritative_sheet_id

EXPECTED_SHEET_ID = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
FAILED_RUN_ID = "42810543146"
ALLOWED_STATES = {"VERIFIED", "FAILED_PARTIAL"}

# Spreadsheet must use IST for NOW() vs exchange-local tick comparisons.
LIVE_AGE = (
    '=IF(C3="MARKET CLOSED","MARKET CLOSED",IFERROR(LET('
    'w,HEARTBEAT!A2,writer,DATEVALUE(LEFT(w,10))+TIMEVALUE(RIGHT(w,8)),'
    'ticks,ARRAYFORMULA(IF(CE_PE_RANK!W5:W204="",0,'
    'IFERROR(DATEVALUE(LEFT(CE_PE_RANK!W5:W204,11))'
    '+TIMEVALUE(RIGHT(CE_PE_RANK!W5:W204,8)),0))),'
    'qage,(NOW()-MIN(ticks))*86400,wage,(NOW()-writer)*86400,'
    'IF(AND(COUNTA(CE_PE_RANK!W5:W204)=200,MIN(ticks)>0,'
    'qage>=-30,qage<=120,wage>=-30,wage<=60),"PASS","FAIL")),"BLOCKED"))'
)
OVERALL = (
    '=IF(OR(COUNTIF(E2:E6,"FAIL")>0,COUNTIF(E2:E6,"BLOCKED")>0,'
    'COUNTIF(E10:E11,"FAIL")>0,COUNTIF(E10:E11,"BLOCKED")>0,'
    'COUNTIF(E2:E6,"#ERROR!")>0,COUNTIF(E10:E11,"#ERROR!")>0,'
    'E2="",E3="",E4="",E5="",E6="",E10="",E11=""),"BLOCKED",'
    'IF(C3="MARKET CLOSED","MARKET CLOSED - alerts are not live",'
    'IF(AND(E3="PASS",E2="PASS",E4="PASS",E5="PASS",E6="PASS",'
    'E10="PASS",OR(E11="PASS",E11="SESSION OPEN")),'
    '"PASS","BLOCKED")))'
)
CLOUD_DT = '(DATEVALUE(LEFT(B5,10))+TIMEVALUE(MID(B5,12,8)))'
CLOUD_AGE = f'=IFERROR(IF(NOW()<{CLOUD_DT},"UNKNOWN",ROUND((NOW()-{CLOUD_DT})*24,1)&"h"),"UNKNOWN")'
CLOUD_STATE = (
    '=IF(UPPER(TRIM(TO_TEXT(B6)))<>"SUCCESS","NO DATA",'
    f'IFERROR(IF(AND((NOW()-{CLOUD_DT})*86400>=0,'
    f'(NOW()-{CLOUD_DT})*86400<=86400),"FRESH","STALE"),"BLOCKED"))'
)
FIXES = {
    "Formula Checks": {
        "C10": '=COUNTA(CE_PE_RANK!A5:A204)&" / 200"',
        "E10": '=IF(COUNTA(CE_PE_RANK!A5:A204)=200,"PASS","FAIL")',
        "C11": '=COUNTIF(CE_PE_RANK!U5:U204,"HIGH MOMENTUM")',
        "E8": OVERALL,
    },
    "CLOUD_STATUS": {"B8": CLOUD_AGE, "B9": CLOUD_STATE},
}


def build_fixes(timezone, failed_run_current):
    fixes = {k: dict(v) for k, v in FIXES.items()}
    fixes["Formula Checks"]["E3"] = (LIVE_AGE if timezone in ("Asia/Kolkata", "Asia/Calcutta")
                                     else '=IF(C3="MARKET CLOSED","MARKET CLOSED","BLOCKED")')
    if failed_run_current:
        fixes["PUBLICATION_STATUS"] = {"A2": "FAILED_PARTIAL"}
        fixes["OPTION_PREDICTIONS"] = {
            "G2": f"Publication: FAILED_STALE_SOURCE (GitHub run {FAILED_RUN_ID})"
        }
    return fixes


def _get_cells(ws, cells, *, render="FORMULA"):
    responses = ws.batch_get(cells, value_render_option=render)
    return {cell: (value[0][0] if value and value[0] else "")
            for cell, value in zip(cells, responses)}


def _write_cells(ws, mapping):
    ws.batch_update([{"range": c, "values": [[v]]} for c, v in mapping.items()],
                    value_input_option="USER_ENTERED")


def audit(book):
    sheets = book.worksheets()
    # The one-time, isolated synthetic receipt is NOT a production dataset.
    # Continue auditing the exact 30 original canonical tabs, and never
    # misclassify the optional demo evidence tab as a new authoritative feed.
    sheets = [ws for ws in sheets if ws.title not in ("MOCK_REPLAY_EVIDENCE", "TRADE_HISTORY_LEDGER")
              and not ws.title.startswith("_ARCHIVE_")]
    if not 24 <= len(sheets) <= 30:
        raise RuntimeError(f"Canonical workbook tab-count drift: expected 24..30 (migration window), got {len(sheets)}")
    print(f"AUDIT_SHEET_ID={EXPECTED_SHEET_ID} AUDIT_TABS={len(sheets)}")
    all_data = {}
    for ws in sheets:
        rows = ws.get_all_values()
        all_data[ws.title] = rows
        content = json.dumps(rows, sort_keys=False, ensure_ascii=False, separators=(",", ":"))
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        errors = sum(str(c).startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#ERROR!"))
                     for row in rows for c in row)
        print(f"AUDIT_TAB={json.dumps(ws.title)} DATA_ROWS={max(0,len(rows)-1)} "
              f"FORMULA_ERRORS={errors} SHA256={checksum}")
    required = {"Formula Checks", "HEARTBEAT", "CE_PE_RANK", "FORENSIC_LIVE",
                "OPTION_PREDICTIONS", "PUBLICATION_STATUS", "CLOUD_STATUS", "WRITE_PROVENANCE"}
    if not required.issubset(all_data):
        raise RuntimeError("Expected forensic tabs absent: " + ",".join(sorted(required-set(all_data))))
    forensic = all_data["FORENSIC_LIVE"]
    symbols = [str(r[1]).strip() for r in forensic[1:] if len(r)>1 and str(r[1]).strip()]
    ranked = all_data["CE_PE_RANK"]
    rank_count = sum(bool(row and str(row[0]).strip()) for row in ranked[4:204])
    duplicates = [name for name, count in Counter(symbols).items() if count>1]
    print(f"AUDIT_UNDERLYINGS={len(symbols)} DISTINCT={len(set(symbols))} "
          f"DUPLICATES={len(duplicates)} AUDIT_RANKED_CONTRACTS={rank_count}")
    pub = all_data["PUBLICATION_STATUS"]
    if len(pub)<2 or len(pub[1])<3:
        raise RuntimeError("PUBLICATION_STATUS is missing current run ID")
    return {"publication_state":pub[1][0], "publication_run":str(pub[1][2]).strip()}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply",action="store_true",
                        help="Apply only the nine authorized repairs, then verify remote readback.")
    args=parser.parse_args(argv)
    if os.environ.get("REAL_BROKER_ORDERS","0")!="0" or os.environ.get("LIVE_ORDER_AUTHORITY","0")!="0":
        raise RuntimeError("Real-order authority must be disabled")
    sheet_id=require_authoritative_sheet_id(os.environ.get("SHEET_ID",""))
    if sheet_id!=EXPECTED_SHEET_ID:
        raise RuntimeError("Canonical Google Sheet ID differs from the owner-provided workbook")
    import gspread
    client=gspread.service_account_from_dict(load_service_account())
    book=client.open_by_key(sheet_id)
    metadata=book.fetch_sheet_metadata()
    props=metadata.get("properties",{})
    timezone=props.get("timeZone","UNKNOWN")
    print("SHEET_TIMEZONE="+timezone+" LOCALE="+str(props.get("locale","UNKNOWN")))
    snapshot=audit(book)
    failed_run_current=(snapshot["publication_run"]==FAILED_RUN_ID
                        and snapshot["publication_state"] in ALLOWED_STATES)
    if not failed_run_current:
        print(f"STALE_RUN_REPAIR_SKIPPED=current_run_{snapshot['publication_run']}")
    fixes=build_fixes(timezone,failed_run_current)
    planned=sum(len(cells) for cells in fixes.values())
    print(f"REPAIR_TARGETS={planned} EXPECTED_NINE_IF_FAILED_RUN={failed_run_current}")
    if not args.apply:
        print("READ_ONLY_AUDIT_COMPLETE")
        return 0
    if snapshot["publication_run"]==FAILED_RUN_ID and not failed_run_current:
        raise RuntimeError("Unexpected publication state, refusing unsafe overwrite")
    for title,cellmap in fixes.items():
        ws=book.worksheet(title)
        before=_get_cells(ws,list(cellmap))
        changed={cell:value for cell,value in cellmap.items() if str(before[cell])!=value}
        if changed:
            _write_cells(ws,changed)
        observed=_get_cells(ws,list(cellmap))
        rendered=_get_cells(ws,list(cellmap),render="FORMATTED_VALUE")
        for cell,expected in cellmap.items():
            actual=str(observed[cell])
            if actual!=expected:
                raise RuntimeError(f"READBACK_MISMATCH:{title}!{cell} expected sha256="
                                   f"{hashlib.sha256(expected.encode()).hexdigest()} actual sha256="
                                   f"{hashlib.sha256(actual.encode()).hexdigest()}")
            display=json.dumps(str(rendered[cell]),ensure_ascii=False)
            print(f"READBACK_PASS {title}!{cell} formula_or_value="
                  f"{json.dumps(actual,ensure_ascii=False)} rendered={display}")
            if str(rendered[cell]).startswith(("#REF!","#ERROR!","#NAME?","#VALUE!")):
                raise RuntimeError(f"RENDERED_FORMULA_ERROR:{title}!{cell}")
    # Critical: failed run must never be labeled VERIFIED after repairs.
    pub=book.worksheet("PUBLICATION_STATUS").acell("A2").value
    if failed_run_current and pub!="FAILED_PARTIAL":
        raise RuntimeError("Failed run still appears as VERIFIED")
    print(f"SHEET_REPAIR_VERIFIED=YES VERIFIED_CELLS={planned} MODE=REAL_SHEET_READBACK "
          "BROKER_VERIFICATION=NOT_CLAIMED")
    return 0


if __name__=="__main__":
    try:sys.exit(main())
    except Exception as exc:
        print(f"SHEET_REPAIR_FAILED={type(exc).__name__}:{exc}",file=sys.stderr)
        sys.exit(1)
