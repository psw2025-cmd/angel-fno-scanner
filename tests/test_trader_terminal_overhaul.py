"""Production workbook migration regression tests: never invent INR profit from signals."""
from decimal import Decimal

import pytest

from paper_log import PAPER_HEADERS
from scripts.sheets.reorganize_trader_terminal import (
    ARCHIVE_PREFIX, DELETE, HIDE, HEADERS, extract_closed, fee_model,
    formulas, formatting_requests, ledger_grid,
)


OMS_HEADERS=["","Trade ID","Timestamp (IST)","Underlying Symbol",
             "Option Contract","Direction / Side","Execution Mode","Qty / Lots",
             "Entry Price (₹)","Stop Loss (-15%)","Target (+50%)","Current Mark (₹)",
             "Exit Price (₹)","Exit Time (IST)","Realized P&L (₹)","Return %",
             "Exit Reason","Trade Status","Data Source"]


def oms_fixture():
    return [
        [""]*19,[""]*19,[""]*19,[""]*19,[""]*19,OMS_HEADERS,
        ["","PT-20261015-001","2026-10-15 09:31:00","FEDERALBNK",
         "FEDERALBNK27OCT26335CE","LONG CE","PAPER_AUTO","5,000","₹7.55",
         "₹6.42","₹11.33","₹11.40","₹11.35","2026-10-15 14:15:00",
         "+₹19,000.00","50.33%","TARGET_REACHED","CLOSED","FORENSIC_LIVE"],
        ["","PT-20261015-003","2026-10-15 10:15:00","ZYDUSLIFE",
         "ZYDUSLIFE27OCT261150CE","LONG CE","PAPER_AUTO","900","₹20.00",
         "₹17.00","₹30.00","₹17.00","₹16.95","2026-10-15 15:10:00",
         "-₹2,745.00","-15.25%","SL_HIT","CLOSED","FORENSIC_LIVE"],
        ["","PT-20261015-009","2026-10-15 10:15:00","LUPIN",
         "LUPIN27OCT261980CE","LONG CE","PAPER_AUTO","425","₹33.50",
         "₹28.48","₹50.25","₹43.50","","",
         "+₹4,250.00","29.8%","","OPEN","FORENSIC_LIVE"]]


def alerts_fixture():
    return [PAPER_HEADERS,
            ["2026-10-15 09:15:00","2026-10-15","FEDERALBNK","CE",
             "335","1.3","FEDERALBNK27OCT26335CE","FEDERALBNK27OCT26335PE",
             "directional only","2.4","2026-10-16 09:15:00"]]


def test_precise_six_deletions_ten_hides_sixteen_columns():
    assert len(DELETE)==6 and len(HIDE)==10
    assert len(set(DELETE+HIDE))==16
    assert len(HEADERS)==16
    assert "TRADE_HISTORY_LEDGER" not in DELETE and "PAPER_TRADING_OMS" not in HIDE
    assert ARCHIVE_PREFIX.startswith("_ARCHIVE_")


def test_only_reconciled_closed_oms_paper_fills_count_as_inr_trades():
    parsed,alerts=extract_closed(oms_fixture(),alerts_fixture())
    assert len(parsed)==2 and alerts==1
    assert [x["gross"] for x in parsed]==[Decimal("19000.00"),Decimal("-2745.00")]
    assert all(x["direction"]=="BUY CE" for x in parsed)
    assert parsed[0]["reason"]=="TARGET_HIT"
    assert parsed[1]["reason"]=="SL_HIT"
    assert parsed[0]["qty"]==Decimal("5000")
    assert parsed[0]["entry"]==Decimal("7.55")
    assert all(t["id"]!="PT-20261015-009" for t in parsed)
    assert all("alert" not in t["id"] for t in parsed)


def test_source_pnl_mismatch_fails_without_fabricated_result():
    source=oms_fixture()
    source[6][14]="+₹19,500"
    with pytest.raises(RuntimeError,match="gross PnL differs"):
        extract_closed(source,alerts_fixture())


def test_broker_mode_cannot_be_assumed_paper_execution():
    source=oms_fixture()
    source[6][6]="LIVE_BROKER"
    with pytest.raises(RuntimeError,match="non-PAPER execution"):
        extract_closed(source,alerts_fixture())


def test_nse_2026_levies_and_explicit_estimated_fee_notice():
    parsed,alerts=extract_closed(oms_fixture(),alerts_fixture())
    t=parsed[0]
    fee=fee_model(t)
    assert fee > Decimal("40")
    n,o,p=formulas(6,t)
    assert "0.0015" in o and "0.0003503" in o and "0.18" in o
    assert "40" in o and "ROUND" in n and "N6-O6" in p
    grid=ledger_grid(parsed,alerts)
    assert len(grid)==7 and grid[4]==HEADERS
    assert "ESTIMATED" in grid[3][0]
    assert "NOT option executions" in grid[3][0]
    assert grid[5][6]==7.55 and grid[5][7]==5000


def test_formatter_freezes_five_rows_and_dark_header():
    requests=formatting_requests(9876,2)
    assert any("updateSheetProperties" in x and x["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"]==5 for x in requests)
    assert any("repeatCell" in x and x["repeatCell"]["range"]["startRowIndex"]==4 and x["repeatCell"]["range"]["endRowIndex"]==5 for x in requests)
    assert sum("mergeCells" in x for x in requests)>=12
