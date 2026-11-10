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
        print(f"TAB title={json.dumps(w.title)} rows={w.row_count} cols={w.col_count} hidden={bool(w._properties.get('hidden',False))}")
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



# --- End-to-end mutation logic. No real broker orders, fake trades or guessed fills. ---
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, date
from hashlib import sha256

HEADERS = [
    "Trade_ID", "Date", "Symbol", "Contract", "Direction (BUY CE / BUY PE)",
    "Entry_Time (IST)", "Entry_Price (\u20b9)", "Quantity (Lots * Lot Size)",
    "Target_Price (\u20b9)", "Stop_Loss (\u20b9)", "Exit_Time (IST)",
    "Exit_Price (\u20b9)", "Exit_Reason (TARGET_HIT / SL_HIT / TRAILING_SL / TIME_EXIT)",
    "Gross_PnL", "Taxes_Brokerage", "Net_PnL",
]
ARCHIVE_PREFIX = "_ARCHIVE_20261111_"
STATUS_TERMINAL = {"CLOSED", "EXITED", "SETTLED"}
EXIT_REASON_MAP = {
    "TARGET_REACHED":"TARGET_HIT", "TARGET_HIT":"TARGET_HIT",
    "SL_HIT":"SL_HIT", "STOP_LOSS":"SL_HIT",
    "STOP_LOSS_HIT":"SL_HIT", "TRAILING_SL":"TRAILING_SL",
    "TRAILING_STOP":"TRAILING_SL", "TIME_EXIT":"TIME_EXIT",
    "TIME_BASED_EXIT":"TIME_EXIT",
}
MONEY_2 = Decimal("0.01")
CHARGE_BROKER = Decimal("40")
CHARGE_STT_NEW = Decimal("0.0015")  # Finance Act 2026; after 2026-04-01
CHARGE_STT_OLD = Decimal("0.001")   # Before April 2026
CHARGE_EXCHANGE = Decimal("0.0003503")  # Indicative NSE options premium turnover
CHARGE_GST = Decimal("0.18")
CHARGE_SEBI = Decimal("0.000001")
CHARGE_STAMP = Decimal("0.00003")


def to_decimal(cell):
    text=str(cell or "").strip().replace(",", "").replace("\u20b9","").replace("Rs.","").replace("+","")
    text=text.replace("INR","").strip()
    if text.startswith("(") and text.endswith(")"):
        text="-"+text[1:-1]
    if not text or not re.fullmatch(r"-?\d+(?:\.\d+)?",text):
        raise ValueError("missing or nonnumeric price / quantity")
    value=Decimal(text)
    if not value.is_finite():
        raise ValueError("non-finite price/quantity")
    return value


def quantize(value):
    return value.quantize(MONEY_2, rounding=ROUND_HALF_UP)


def source_digest(rows):
    return sha256(json.dumps(rows,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()


def parse_ist(value):
    # All OMS closed executions must carry a real exchange-local timestamp.
    s=str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M",
                    "%d-%b-%Y %H:%M:%S","%d-%b-%Y %H:%M"):
        try:
            return datetime.strptime(s,pattern)
        except ValueError:
            continue
    raise ValueError("invalid IST execution timestamp")


def extract_closed(oms_rows, alert_rows):
    if len(oms_rows)<7 or len(oms_rows[5])<19:
        raise RuntimeError("PAPER_TRADING_OMS header at row 6 absent; ledger import blocked")
    expected={"Trade ID":1,"Timestamp (IST)":2,"Underlying Symbol":3,
              "Option Contract":4,"Direction / Side":5,"Execution Mode":6,
              "Qty / Lots":7,"Entry Price (\u20b9)":8,"Exit Price (\u20b9)":12,
              "Exit Time (IST)":13,"Realized P&L (\u20b9)":14,
              "Exit Reason":16,"Trade Status":17}
    header=oms_rows[5]
    missing=[name for name,idx in expected.items() if str(header[idx]).strip()!=name]
    if missing:
        raise RuntimeError("OMS column contract drift: "+", ".join(missing))
    # PAPER_ALERT_LOG tracks spot/future % outcomes, not premium fills or
    # option quantities; those cannot be converted into realized INR PnL.
    if not alert_rows or not {"Logged at IST","Later session change %","Outcome filled at"}.issubset(set(alert_rows[0])):
        raise RuntimeError("PAPER_ALERT_LOG schema drift")
    outcome_count=sum(len(r)>10 and str(r[10]).strip()!="" for r in alert_rows[1:])
    rows=[]
    rejected=[]
    used=set()
    for pos,record in enumerate(oms_rows[6:],start=7):
        r=list(record)+[""]*(19-len(record))
        status=str(r[17]).strip().upper()
        if status not in STATUS_TERMINAL:
            continue
        trade_id=str(r[1]).strip()
        try:
            if not trade_id or trade_id in used:raise ValueError("missing/duplicate Trade ID")
            if str(r[6]).strip().upper() not in ("PAPER_AUTO","PAPER_MANUAL","SIMULATED","PAPER"):
                raise ValueError("non-PAPER execution cannot be assumed broker-verified")
            symbol=str(r[3]).strip().upper()
            contract=str(r[4]).strip().upper()
            if not symbol or not contract or not contract.endswith(("CE","PE")):
                raise ValueError("invalid option identity")
            side=str(r[5]).strip().upper()
            direction="BUY CE" if side in ("LONG CE","BUY CE","BUY_CE") else (
                "BUY PE" if side in ("LONG PE","BUY PE","BUY_PE") else "")
            if not direction or not contract.endswith(direction[-2:]):
                raise ValueError("direction and option contract mismatch")
            entry_t=parse_ist(r[2])
            exit_t=parse_ist(r[13])
            if exit_t<=entry_t:raise ValueError("noncausal exit")
            qty=to_decimal(r[7]);entry=to_decimal(r[8])
            stop=to_decimal(r[9]);target=to_decimal(r[10]);exit_price=to_decimal(r[12])
            if qty<=0 or qty!=qty.to_integral_value() or entry<=0 or exit_price<0 or stop<=0 or target<=0:
                raise ValueError("invalid fill price or quantity")
            reason=EXIT_REASON_MAP.get(str(r[16]).strip().upper())
            if not reason:raise ValueError("exit reason unrecognized")
            gross=quantize((exit_price-entry)*qty)
            source_pnl=quantize(to_decimal(r[14]))
            if abs(gross-source_pnl)>Decimal("0.02"):
                raise ValueError("source gross PnL differs from entry/exit/quantity")
            used.add(trade_id)
            rows.append({
                "id":trade_id,"date":entry_t.date().isoformat(),"symbol":symbol,
                "contract":contract,"direction":direction,
                "entry_t":entry_t.strftime("%Y-%m-%d %H:%M:%S"),
                "exit_t":exit_t.strftime("%Y-%m-%d %H:%M:%S"),
                "entry":entry,"qty":qty,"target":target,"stop":stop,
                "exit":exit_price,"reason":reason,"gross":gross,
                "source_row":pos,
            })
        except (ValueError,InvalidOperation) as exc:
            rejected.append({"source_row":pos,"reason":str(exc)})
    # Never silently collapse an actually closed OMS execution into an omitted
    # row: that could materially misstate profit metrics.
    if rejected:
        raise RuntimeError("OMS closed-fill validation failed: "+json.dumps(rejected,ensure_ascii=False))
    rows.sort(key=lambda r:(r["exit_t"],r["id"]))
    return rows,outcome_count


def fee_model(trade):
    entry=trade["entry"];exit_price=trade["exit"];qty=trade["qty"]
    buy=entry*qty;sell=exit_price*qty;turnover=buy+sell
    rate=CHARGE_STT_NEW if trade["date"]>="2026-04-01" else CHARGE_STT_OLD
    exchange=turnover*CHARGE_EXCHANGE
    sebi=turnover*CHARGE_SEBI
    return quantize(sell*rate+exchange+sebi+buy*CHARGE_STAMP+
                    CHARGE_BROKER+CHARGE_GST*(CHARGE_BROKER+exchange+sebi))


def formulas(index,trade):
    stt=CHARGE_STT_NEW if trade["date"]>="2026-04-01" else CHARGE_STT_OLD
    i=str(index)
    gross=f"=ROUND((L{i}-G{i})*H{i},2)"
    exch=f"((G{i}+L{i})*H{i}*{CHARGE_EXCHANGE})"
    sebi=f"((G{i}+L{i})*H{i}*{CHARGE_SEBI})"
    stt_part=f"(L{i}*H{i}*{stt})"
    stamp=f"(G{i}*H{i}*{CHARGE_STAMP})"
    cost=f"=ROUND({stt_part}+{exch}+{sebi}+{stamp}+{CHARGE_BROKER}+{CHARGE_GST}*({CHARGE_BROKER}+{exch}+{sebi}),2)"
    net=f"=ROUND(N{i}-O{i},2)"
    return [gross,cost,net]


def ledger_grid(trades,alert_outcomes):
    total=len(trades)
    title="TRADE HISTORY | PAPER-ONLY FILLS | NOT BROKER-VERIFIED"
    label=[title]+[""]*15
    metrics=[""]*16
    for slot,text in ((0,"Total Realized Net P&L (\u20b9)"),(4,"Win Rate %"),
                      (7,"Profit Factor"),(10,"Total Trades"),(13,"Avg Win / Avg Loss")):
        metrics[slot]=text
    summary=[""]*16
    summary[0]='=IF(K3=0,"N/A",ROUND(SUM(P6:P),2))'
    summary[4]='=IF(K3=0,"N/A",COUNTIF(P6:P,">0")/K3)'
    summary[7]='=IF(K3=0,"N/A",IF(ABS(SUMIF(P6:P,"<0",P6:P))=0,IF(SUMIF(P6:P,">0",P6:P)>0,"\u221e","N/A"),SUMIF(P6:P,">0",P6:P)/ABS(SUMIF(P6:P,"<0",P6:P))))'
    summary[10]='=COUNTA(A6:A)'
    summary[13]='=IF(K3=0,"N/A",IFERROR("\u20b9"&TEXT(AVERAGEIF(P6:P,">0",P6:P),"#,##0.00"),"N/A")&" / "&IFERROR("\u20b9"&TEXT(ABS(AVERAGEIF(P6:P,"<0",P6:P)),"#,##0.00"),"N/A"))'
    note=(f"PAPER execution history: {total} OMS CLOSED fills. "
          f"{alert_outcomes} directional futures-alert outcomes are NOT option executions and are retained in PAPER_ALERT_LOG. "
          "Gross premium PnL reconciled to OMS; net PnL uses ESTIMATED NSE taxes / flat \u20b940 brokerage; actual contract-note fees not available.")
    row4=[note]+[""]*15
    data=[]
    for t in trades:
        data.append([t["id"],t["date"],t["symbol"],t["contract"],t["direction"],
                    t["entry_t"],float(t["entry"]),int(t["qty"]),float(t["target"]),
                    float(t["stop"]),t["exit_t"],float(t["exit"]),t["reason"],"","",""])
    return [label,metrics,summary,row4,HEADERS,*data]


def color(rgb):
    return {"red":rgb[0]/255,"green":rgb[1]/255,"blue":rgb[2]/255}


def formatting_requests(sheet_id,trades_count):
    # Institution-style navy KPI, muted cyan metric bands, adaptive widths.
    navy=color((12,28,51));navy2=color((20,49,85))
    dark=color((9,22,44));light=color((232,240,249));white=color((255,255,255))
    requests=[]
    def rg(row0,row1,col0=0,col1=16):
        return {"sheetId":sheet_id,"startRowIndex":row0,"endRowIndex":row1,
                "startColumnIndex":col0,"endColumnIndex":col1}
    for row in (0,3):
        requests.append({"mergeCells":{"range":rg(row,row+1),"mergeType":"MERGE_ALL"}})
    spans=[(0,4),(4,7),(7,10),(10,13),(13,16)]
    for start,end in spans:
        for row in (1,2):
            requests.append({"mergeCells":{"range":rg(row,row+1,start,end),
                                           "mergeType":"MERGE_ALL"}})
    requests.append({"updateSheetProperties":{
        "properties":{"sheetId":sheet_id,
                      "gridProperties":{"frozenRowCount":5,"hideGridlines":True}},
        "fields":"gridProperties.frozenRowCount,gridProperties.hideGridlines"}})
    for row,background,size,fg in ((0,dark,17,white),(1,navy,10,light),
                                    (2,navy2,17,white),(3,light,10,navy),
                                    (4,navy,10,white)):
        requests.append({"repeatCell":{
            "range":rg(row,row+1),
            "cell":{"userEnteredFormat":{
                "backgroundColor":background,
                "textFormat":{"foregroundColor":fg,"bold":row!=3,"fontSize":size},
                "verticalAlignment":"MIDDLE",
                "horizontalAlignment":("LEFT" if row in (0,3,4) else "CENTER"),
                "wrapStrategy":"CLIP"}},
            "fields":"userEnteredFormat"}})
    for col,width in enumerate((165,112,125,220,136,163,128,155,130,125,163,130,184,140,150,145)):
        requests.append({"updateDimensionProperties":{
            "range":{"sheetId":sheet_id,"dimension":"COLUMNS",
                     "startIndex":col,"endIndex":col+1},
            "properties":{"pixelSize":width},"fields":"pixelSize"}})
    for row,pix in ((0,37),(1,28),(2,43),(3,28),(4,37)):
        requests.append({"updateDimensionProperties":{
            "range":{"sheetId":sheet_id,"dimension":"ROWS",
                     "startIndex":row,"endIndex":row+1},
            "properties":{"pixelSize":pix},"fields":"pixelSize"}})
    for column in (6,8,9,11,13,14,15):
        requests.append({"repeatCell":{
            "range":rg(5,max(6,6+trades_count),column,column+1),
            "cell":{"userEnteredFormat":{
                "numberFormat":{"type":"CURRENCY","pattern":"\u20b9#,##0.00;[Red]-\u20b9#,##0.00"}}},
            "fields":"userEnteredFormat.numberFormat"}})
    requests.append({"repeatCell":{
        "range":rg(2,3,4,7),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"PERCENT","pattern":"0.00%"}}},
        "fields":"userEnteredFormat.numberFormat"}})
    requests.append({"repeatCell":{
        "range":rg(2,3,0,4),
        "cell":{"userEnteredFormat":{"numberFormat":{"type":"CURRENCY","pattern":"\u20b9#,##0.00;[Red]-\u20b9#,##0.00"}}},
        "fields":"userEnteredFormat.numberFormat"}})
    requests.append({"setBasicFilter":{"filter":{"range":rg(4,max(6,6+trades_count))}}})
    return requests


def archive_and_remove(book):
    found={w.title:w for w in book.worksheets()}
    removed=[]
    archived=[]
    for name in DELETE:
        if name not in found:
            if ARCHIVE_PREFIX+name not in found:
                raise RuntimeError("Legacy tab missing WITHOUT preserved archive: "+name)
            continue
        original=book.worksheet(name)
        snapshot=original.get_all_values()
        backup_title=ARCHIVE_PREFIX+name
        if backup_title in {w.title for w in book.worksheets()}:
            backup=book.worksheet(backup_title)
        else:
            backup=original.duplicate(new_sheet_name=backup_title)
        # Freeze historical display VALUES: original formulas referencing soon
        # to-be-deleted tabs must not turn the archive into #REF! after purge.
        if snapshot:
            width=max(len(r) for r in snapshot)
            rows=[list(r)+[""]*(width-len(r)) for r in snapshot]
            from gspread.utils import rowcol_to_a1
            right=rowcol_to_a1(len(snapshot),width)
            backup.update(range_name=f"A1:{right}",values=rows,value_input_option="RAW")
        actual=backup.get_all_values()
        if source_digest(actual)!=source_digest(snapshot):
            raise RuntimeError("Archive readback failed; refusing deletion: "+name)
        if not backup.isSheetHidden:backup.hide()
        book.del_worksheet(original)
        removed.append(name)
        archived.append(backup_title)
        print(f"ARCHIVED_AND_DELETED={name} archived_rows={len(snapshot)}")
    return removed,archived


def build_ledger(book,trades,alert_outcomes):
    try:
        ledger=book.worksheet("TRADE_HISTORY_LEDGER")
        new=False
    except Exception as exc:
        if exc.__class__.__name__!="WorksheetNotFound":raise
        pred=book.worksheet("OPTION_PREDICTIONS")
        ledger=book.add_worksheet(title="TRADE_HISTORY_LEDGER",
                                   rows=max(150,len(trades)+10),cols=16,index=pred.index+1)
        new=True
    layout=ledger_grid(trades,alert_outcomes)
    if ledger.row_count < max(150,len(trades)+10):
        ledger.resize(rows=max(150,len(trades)+10),cols=16)
    # Only replace the dedicated ledger. All source alerts and paper OMS rows
    # are immutable in this migration.
    ledger.batch_clear([f"A1:P{ledger.row_count}"])
    ledger.update(range_name=f"A1:P{len(layout)}",values=layout,value_input_option="RAW")
    updates=[]
    for i in range(6,6+len(trades)):
        updates.append({"range":f"N{i}:P{i}","values":[formulas(i,trades[i-6])]})
    if updates:ledger.batch_update(updates,value_input_option="USER_ENTERED")
    # Update KPI formula row after raw-grid construction.
    metric=layout[2]
    ledger.batch_update([{"range":f"{col}3","values":[[metric[index]]]}
                         for col,index in (("A",0),("E",4),("H",7),("K",10),("N",13))],
                        value_input_option="USER_ENTERED")
    if new:
        book.batch_update({"requests":formatting_requests(ledger.id,len(trades))})
    pred=book.worksheet("OPTION_PREDICTIONS")
    ledger.update_index(pred.index+1)
    if ledger.isSheetHidden:ledger.show()
    ledger.update_tab_color("#153967")
    return ledger


def verify_ledger(ledger,trades):
    if ledger.get("A5:P5") != [HEADERS]:
        raise RuntimeError("Trade ledger header readback mismatch")
    if ledger.index != ledger.spreadsheet.worksheet("OPTION_PREDICTIONS").index+1:
        raise RuntimeError("Trade ledger not adjacent to OPTION_PREDICTIONS")
    source_total=Decimal("0")
    wins=0;positive=Decimal(0);negative=Decimal(0)
    read_rows=ledger.get(f"A6:P{5+len(trades)}",value_render_option="UNFORMATTED_VALUE") if trades else []
    if len(read_rows)!=len(trades):raise RuntimeError("Ledger row-count mismatch")
    for i,(trade,row) in enumerate(zip(trades,read_rows),start=6):
        if len(row)!=16 or str(row[0])!=trade["id"]:
            raise RuntimeError(f"Source ID or formula output missing at row {i}")
        gross=quantize(Decimal(str(row[13])))
        fees=quantize(Decimal(str(row[14])))
        net=quantize(Decimal(str(row[15])))
        expected_gross=trade["gross"];expected_fees=fee_model(trade)
        expected_net=quantize(expected_gross-expected_fees)
        if gross!=expected_gross or abs(fees-expected_fees)>Decimal("0.01") or abs(net-expected_net)>Decimal("0.01"):
            raise RuntimeError(f"Financial readback mismatch at row {i}: gross={gross} fees={fees} net={net}")
        source_total+=net
        if net>0:wins+=1;positive+=net
        elif net<0:negative+=net
    total=len(trades)
    expected_win_rate=Decimal(wins)/Decimal(total) if total else Decimal(0)
    expected_pf=(positive/abs(negative)) if negative else None
    actual_trades=ledger.acell("K3",value_render_option="UNFORMATTED_VALUE").value
    actual_net=ledger.acell("A3",value_render_option="UNFORMATTED_VALUE").value
    actual_win=ledger.acell("E3",value_render_option="UNFORMATTED_VALUE").value
    actual_pf=ledger.acell("H3",value_render_option="UNFORMATTED_VALUE").value
    actual_avg=ledger.acell("N3",value_render_option="FORMATTED_VALUE").value
    if int(float(actual_trades))!=total:raise RuntimeError("KPI trade count incorrect")
    if total:
        if abs(Decimal(str(actual_net))-source_total)>Decimal("0.01"):
            raise RuntimeError("KPI net PnL does not reconcile")
        if abs(Decimal(str(actual_win))-expected_win_rate)>Decimal("0.00001"):
            raise RuntimeError("KPI win rate does not reconcile")
        if expected_pf is not None and abs(Decimal(str(actual_pf))-expected_pf)>Decimal("0.001"):
            raise RuntimeError("KPI profit factor does not reconcile")
    else:
        if str(actual_net)!="N/A":raise RuntimeError("Empty ledger PnL must be N/A")
    print(f"LEDGER_READBACK_PASS_ROWS={total} GROSS_SUM_INR={sum((t['gross'] for t in trades),Decimal(0))}")
    print(f"KPI_READBACK_TRADES={actual_trades} KPI_READBACK_NET_PNL_INR={actual_net}")
    print(f"KPI_READBACK_WIN_RATE={actual_win} KPI_READBACK_PROFIT_FACTOR={actual_pf}")
    print(f"KPI_READBACK_AVG_WIN_LOSS={actual_avg}")
    print("NET_PNL_BASIS=ESTIMATED_FEES_NOT_BROKER_CONTRACT_NOTE")
    return {
        "verified_rows":total,"net_inr":str(source_total),"gross_inr":
            str(sum((t["gross"] for t in trades),Decimal(0))),
        "win_rate":str(actual_win),"profit_factor":str(actual_pf),
        "avg_win_loss":str(actual_avg),
    }


def apply(book):
    required={"OPTION_PREDICTIONS","PAPER_TRADING_OMS","PAPER_ALERT_LOG"}
    present={w.title for w in book.worksheets()}
    if not required.issubset(present):raise RuntimeError("Source trading tabs missing")
    # Only the PAPER OMS has entry/exit premium and contract quantity.
    oms=book.worksheet("PAPER_TRADING_OMS").get_all_values()
    alerts=book.worksheet("PAPER_ALERT_LOG").get_all_values()
    oms_sha=source_digest(oms);alerts_sha=source_digest(alerts)
    trades,outcome_count=extract_closed(oms,alerts)
    print(f"SOURCE_OMS_CLOSED_COMPLETE={len(trades)} SIGNAL_OUTCOMES_DIRECTIONAL_ONLY={outcome_count}")
    ledger=build_ledger(book,trades,outcome_count)
    verify=verify_ledger(ledger,trades)
    removed,archives=archive_and_remove(book)
    hidden=[]
    for name in HIDE:
        try:ws=book.worksheet(name)
        except Exception as e:raise RuntimeError("Required internal telemetry missing: "+name) from e
        if not ws.isSheetHidden:ws.hide()
        hidden.append(name)
    if book.worksheet("PAPER_TRADING_OMS").get_all_values()!=oms:
        raise RuntimeError("PAPER_TRADING_OMS data altered during reorganization")
    if source_digest(book.worksheet("PAPER_ALERT_LOG").get_all_values())!=alerts_sha:
        raise RuntimeError("PAPER_ALERT_LOG was modified")
    visible=[];invisible=[]
    for w in book.worksheets():
        (invisible if w.isSheetHidden else visible).append(w.title)
    if any(x in visible for x in HIDE) or any(x in visible for x in archives):
        raise RuntimeError("Telemetry/archive tab became visible after overhaul")
    if any(x in visible+invisible for x in DELETE):
        raise RuntimeError("Dead legacy tabs remain")
    if "TRADE_HISTORY_LEDGER" not in visible:
        raise RuntimeError("Trade ledger not visible")
    if any(x not in invisible for x in HIDE):
        raise RuntimeError("Hidden telemetry readback mismatch")
    if source_digest(book.worksheet("PAPER_TRADING_OMS").get_all_values())!=oms_sha:
        raise RuntimeError("Original PAPER OMS history changed")
    print("DELETED_TAB_COUNT="+str(len(removed)))
    print("DELETED_TABS="+json.dumps(removed))
    print("HIDDEN_TELEMETRY_TABS="+json.dumps(hidden))
    print("PRESERVED_HIDDEN_ARCHIVES="+json.dumps(archives))
    print("VISIBLE_TABS="+json.dumps(visible,ensure_ascii=False))
    print("HIDDEN_TABS="+json.dumps(invisible,ensure_ascii=False))
    print("TRADE_HISTORY_LEDGER_ROW_COUNT="+str(verify["verified_rows"]))
    print("TRADE_TERMINAL_OVERHAUL_READBACK=PASS")
    return verify

def main():
    p=argparse.ArgumentParser()
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect",action="store_true")
    group.add_argument("--apply",action="store_true")
    args=p.parse_args()
    sh=connect()
    if args.inspect:inspect(sh)
    else:apply(sh)


if __name__=="__main__":main()
