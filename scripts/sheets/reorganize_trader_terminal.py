#!/usr/bin/env python3
"""OPTION_SHEET forensic inspect and safe trader-terminal migration.

--inspect never mutates workbook. --apply implemented only after reviewing
source schema and reference impact. Live and simulated records stay separate.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter

from credentials import load_service_account, require_authoritative_sheet_id

CANONICAL = "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs"
DELETE = (
    "Sheet1","Sheet2","Sheet3","LEGACY_F&O_DASHBOARD_OBJECT",
    "E2E_AUDIT_20260928","MARKET_LEARNINGS_20260928",
)
HIDE = (
    "MOCK_REPLAY_EVIDENCE","PUBLICATION_STATUS","WRITE_PROVENANCE",
    "CLOUD_STATUS","PUBLIC_SYNC_LOG","HEARTBEAT","FORENSIC_LIVE",
    "Formula Checks","SYSTEM_RESOLUTION_TRACKER","Cloud_Automation_Setup",
)
def connect():
    if os.getenv("LIVE_ORDER_AUTHORITY","0")!="0" or os.getenv("REAL_BROKER_ORDERS","0")!="0":
        raise RuntimeError("real-order authority not disabled")
    sheet_id=require_authoritative_sheet_id(os.getenv("SHEET_ID",""))
    if sheet_id!=CANONICAL:
        raise RuntimeError("different workbook than canonical OPTION_SHEET")
    import gspread
    return gspread.service_account_from_dict(load_service_account()).open_by_key(sheet_id)


def mask(v):
    s=str(v).strip()
    if not s:return ""
    if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{2}:\d{2}",s):
        return "<DATE_OR_TIME>"
    if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)*%?",s):
        return "<NUMBER>"
    return s[:68]


def inspect(book):
    sheets=book.worksheets()
    names={w.title for w in sheets}
    print("READ_ONLY_TERMINAL_DISCOVERY=1 TOTAL_TABS="+str(len(sheets)))
    for w in sheets:
        print(f"TAB title={json.dumps(w.title)} rows={w.row_count} cols={w.col_count} hidden={bool(w._properties.get("hidden",False))}")
    print("DELETE_CANDIDATES_PRESENT="+json.dumps([s for s in DELETE if s in names]))
    print("HIDE_CANDIDATES_PRESENT="+json.dumps([s for s in HIDE if s in names]))
    for tab in ["PAPER_TRADING_OMS","PAPER_ALERT_LOG"]:
        ws=book.worksheet(tab)
        grid=ws.get_all_values()
        print(f"SOURCE={tab} ROWS={len(grid)} HEADER={json.dumps(grid[0][:30],ensure_ascii=False) if grid else 'EMPTY'}")
        for i,row in enumerate(grid[:25],1):
            print(f"SCHEMA_SAMPLE {tab}:{i} WIDTH={len(row)} CELLS={json.dumps([mask(x) for x in row[:24]],ensure_ascii=False)}")
        print(f"MARKER_COUNTS_{tab}="+json.dumps(Counter(
            token for row in grid[1:] for cell in row
            for token in re.findall(r"\b(?:CLOSED|FILLED|EXIT|TARGET_HIT|SL_HIT|TRAILING_SL|TIME_EXIT|SIMULATED|REALIZED)\b",str(cell).upper())
        ).most_common(15)))
        if tab=="PAPER_ALERT_LOG":
            print("ALERT_LATER_FILLED="+str(sum(len(row)>10 and bool(str(row[10]).strip()) for row in grid[1:])))
    for name in DELETE:
        if name in names:
            rows=book.worksheet(name).get_all_values()
            print(f"DELETE_SOURCE={json.dumps(name)} NONEMPTY_ROWS={len(rows)}")
    for w in sheets:
        if w.title in DELETE: continue
        # Formula dependency search is read-only, and prevents #REF on source deletion.
        if w.title in ("TRADE_HISTORY_LEDGER",): continue
        all_formulas=w.get_all_values(value_render_option="FORMULA")
        hits=Counter()
        for row in all_formulas:
            for cell in row:
                if isinstance(cell,str) and cell.startswith("="):
                    for dead in DELETE:
                        if re.search(re.escape(dead)+r"!",cell,re.I) or f"'{dead}'!" in cell:
                            hits[dead]+=1
        if hits:
            print("DEPENDENCY_WARN="+json.dumps({"tab":w.title,"refs":hits}))
    print("INSPECT_EXIT_0_SOURCE_DATA_UNMODIFIED")


def main():
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--apply",action="store_true")
    args=p.parse_args()
    sh=connect()
    if args.inspect:inspect(sh)
    else:raise RuntimeError("--apply not enabled before source-schema audit and backup")


if __name__=="__main__":main()
