"""Honest cloud status for paper entries and exits.

This module records only rows that already have a real entry price.
It does not invent trades, hit rates, or a healthy flag.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import re
from pathlib import Path
from typing import Sequence

LEDGER_HEADER = [
    "trade_id",
    "symbol",
    "option_type",
    "strike",
    "expiry",
    "entry_time",
    "entry_price",
    "exit_time",
    "exit_price",
    "quantity",
    "stop_loss",
    "take_profit",
    "fees",
    "realized_pnl",
    "status",
    "source_run_id",
]

PLACEHOLDER_SYMBOLS = {
    "SAMPLE",
    "TEST",
    "DEMO",
    "FAKE",
    "DUMMY",
    "XXX",
    "TBD",
    "PLACEHOLDER",
    "N/A",
    "NA",
}

_ENTRY_PRICE = re.compile(r"Entry:\s*\u20b9?\s*([0-9]+(?:\.[0-9]+)?)")
_EXIT_PRICE = re.compile(r"exit\s+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_STOP = re.compile(r"SL:\s*\u20b9?\s*([0-9]+(?:\.[0-9]+)?)")
_TARGET = re.compile(r"Target:\s*\u20b9?\s*([0-9]+(?:\.[0-9]+)?)")
_EXIT_WORD = re.compile(r"\b(WIN|LOSS|SCRATCH)\b")
STALE_AFTER = dt.timedelta(hours=36)


def option_exit_recorded(text: str) -> bool:
    """True only when an option exit rule has already classified the row."""
    return _EXIT_WORD.search(str(text or "").upper()) is not None


def quote_attempt_covers_day(text: str, day: str) -> bool:
    """A NO DATA stamp for this session is an attempt, not a fill."""
    raw = str(text or "").strip().upper()
    return raw.startswith("NO DATA") and str(day) in raw


def _positive(value) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _symbol_ok(symbol: str) -> bool:
    cleaned = str(symbol or "").strip().upper()
    if not cleaned or cleaned in PLACEHOLDER_SYMBOLS:
        return False
    if cleaned.startswith("TEST") or cleaned.startswith("SAMPLE") or cleaned.startswith("FAKE"):
        return False
    return True


def trade_key(session_date: str, symbol: str, side: str, contract: str) -> str:
    return "|".join([
        str(session_date or "").strip(),
        str(symbol or "").strip().upper(),
        str(side or "").strip().upper(),
        str(contract or "").strip().upper(),
    ])


def _parse_stamp(value: str):
    raw = str(value or "").strip()[:19]
    try:
        return dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _naive_ist(now):
    if now is None:
        return None
    if getattr(now, "tzinfo", None) is not None:
        from zoneinfo import ZoneInfo
        return now.astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)
    return now


def _cell(row: Sequence, index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index] or "")


def _header_index(header: Sequence[str], name: str) -> int | None:
    for index, cell in enumerate(header):
        if str(cell).strip().lower() == name.lower():
            return index
    return None


def ledger_rows_from_alerts(values: Sequence[Sequence], run_id: str = "") -> list[dict]:
    """Build ledger rows from overnight alerts that already contain an entry price."""
    if not values:
        return []
    header = [str(cell) for cell in values[0]]
    columns = {
        "logged": _header_index(header, "Logged at IST"),
        "session": _header_index(header, "Session date"),
        "symbol": _header_index(header, "Symbol"),
        "side": _header_index(header, "Side"),
        "ce": _header_index(header, "CE contract"),
        "pe": _header_index(header, "PE contract"),
        "note": _header_index(header, "Note"),
        "later": _header_index(header, "Later session change %"),
        "filled": _header_index(header, "Outcome filled at"),
    }
    if columns["symbol"] is None or columns["note"] is None:
        return []
    rows = []
    for raw in values[1:]:
        note = _cell(raw, columns["note"])
        if "[OVERNIGHT" not in note.upper():
            continue
        symbol = _cell(raw, columns["symbol"]).strip().upper()
        side = _cell(raw, columns["side"]).strip().upper()
        if not _symbol_ok(symbol) or side not in ("CE", "PE"):
            continue
        entry_match = _ENTRY_PRICE.search(note)
        if not entry_match or not _positive(entry_match.group(1)):
            continue
        contract = _cell(raw, columns["ce"] if side == "CE" else columns["pe"]).strip().upper()
        later = _cell(raw, columns["later"])
        exit_match = _EXIT_PRICE.search(later)
        stop_match = _STOP.search(note)
        target_match = _TARGET.search(note)
        closed = option_exit_recorded(later) and exit_match is not None and _positive(exit_match.group(1))
        row = {key: "" for key in LEDGER_HEADER}
        row.update({
            "trade_id": trade_key(_cell(raw, columns["session"]), symbol, side, contract),
            "symbol": symbol,
            "option_type": side,
            "entry_time": _cell(raw, columns["logged"]).strip(),
            "entry_price": entry_match.group(1),
            "exit_time": _cell(raw, columns["filled"]).strip() if closed else "",
            "exit_price": exit_match.group(1) if closed else "",
            "stop_loss": stop_match.group(1) if stop_match else "",
            "take_profit": target_match.group(1) if target_match else "",
            "status": "CLOSED" if closed else "OPEN",
            "source_run_id": str(run_id or ""),
        })
        rows.append(row)
    return rows


def apply_exit_updates(rows: Sequence[dict], reconciled: Sequence[dict]) -> list[dict]:
    """Attach a real option exit price. Rows without a price stay open."""
    by_id = {row["trade_id"]: dict(row) for row in rows if row.get("trade_id")}
    for result in reconciled or []:
        if not isinstance(result, dict):
            continue
        if not _symbol_ok(result.get("symbol", "")):
            continue
        if not _positive(result.get("actual_open_ltp")) or not _positive(result.get("entry_ltp")):
            continue
        if result.get("outcome") not in ("WIN", "LOSS", "SCRATCH"):
            continue
        key = trade_key(
            result.get("trade_date", ""),
            result.get("symbol", ""),
            result.get("side", ""),
            result.get("contract") or result.get("forecast_contract") or "",
        )
        current = by_id.get(key)
        if current is None:
            continue
        current["exit_price"] = str(result["actual_open_ltp"])
        current["exit_time"] = str(result.get("reconciled_at_ist") or "")
        current["status"] = "CLOSED"
        current["realized_pnl"] = ""
        by_id[key] = current
    return list(by_id.values())


def _read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            if not raw:
                continue
            row = {key: str(raw.get(key) or "") for key in LEDGER_HEADER}
            if row.get("trade_id") and _symbol_ok(row.get("symbol", "")) and _positive(row.get("entry_price")):
                rows.append(row)
        return rows


def _write_ledger(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: (row.get("entry_time", ""), row.get("trade_id", "")))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_HEADER, lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            if not _symbol_ok(row.get("symbol", "")) or not _positive(row.get("entry_price")):
                continue
            safe = {key: row.get(key, "") for key in LEDGER_HEADER}
            if safe.get("status") == "CLOSED" and not _positive(safe.get("exit_price")):
                safe["status"] = "OPEN"
                safe["exit_price"] = ""
                safe["exit_time"] = ""
            safe["realized_pnl"] = ""
            safe["quantity"] = ""
            safe["fees"] = ""
            writer.writerow(safe)


def upsert_paper_ledger(path, updates: Sequence[dict]) -> int:
    """Merge real rows into the ledger. Refuses placeholder rows and priceless exits."""
    incoming = []
    for row in updates or []:
        if not _symbol_ok(row.get("symbol", "")) or not _positive(row.get("entry_price")):
            continue
        if str(row.get("status", "")).upper() == "CLOSED" and not _positive(row.get("exit_price")):
            continue
        incoming.append(row)
    if not incoming:
        return 0
    target = Path(path)
    by_id = {row["trade_id"]: row for row in _read_ledger(target)}
    changed = 0
    for row in incoming:
        current = by_id.get(row["trade_id"])
        if current is None:
            by_id[row["trade_id"]] = {
                key: ("" if key in ("quantity", "fees", "realized_pnl") else row.get(key, ""))
                for key in LEDGER_HEADER
            }
            stored = by_id[row["trade_id"]]
            if not _positive(stored.get("exit_price")):
                stored["status"] = "OPEN"
                stored["exit_price"] = ""
                stored["exit_time"] = ""
            else:
                stored["status"] = "CLOSED"
            changed += 1
            continue
        if _positive(row.get("exit_price")) and row.get("status") == "CLOSED":
            current["exit_price"] = str(row["exit_price"])
            current["exit_time"] = str(row.get("exit_time") or "")
            current["status"] = "CLOSED"
            current["realized_pnl"] = ""
            changed += 1
    if changed:
        _write_ledger(target, list(by_id.values()))
    return changed


def default_ledger_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "paper_trades.csv"


def _overnight_facts(values: Sequence[Sequence]) -> dict:
    facts = {
        "entries": [],
        "latest": None,
        "read": bool(values),
    }
    if not values:
        return facts
    header = [str(cell) for cell in values[0]]
    columns = {
        "logged": _header_index(header, "Logged at IST"),
        "session": _header_index(header, "Session date"),
        "symbol": _header_index(header, "Symbol"),
        "side": _header_index(header, "Side"),
        "note": _header_index(header, "Note"),
        "later": _header_index(header, "Later session change %"),
        "filled": _header_index(header, "Outcome filled at"),
    }
    if columns["symbol"] is None or columns["note"] is None:
        facts["read"] = False
        return facts
    for raw in values[1:]:
        note = _cell(raw, columns["note"])
        if "[OVERNIGHT" not in note.upper():
            continue
        symbol = _cell(raw, columns["symbol"]).strip().upper()
        side = _cell(raw, columns["side"]).strip().upper()
        if not _symbol_ok(symbol) or side not in ("CE", "PE"):
            continue
        entry_match = _ENTRY_PRICE.search(note)
        if not entry_match or not _positive(entry_match.group(1)):
            continue
        later = _cell(raw, columns["later"]).strip()
        logged = _cell(raw, columns["logged"]).strip()
        stamp = _parse_stamp(logged)
        if stamp is not None and (facts["latest"] is None or stamp > facts["latest"]):
            facts["latest"] = stamp
        if option_exit_recorded(later):
            state = "CLOSED"
        elif later.upper().startswith("NO DATA"):
            state = "NO DATA"
        else:
            state = "OPEN"
        exit_match = _EXIT_PRICE.search(later)
        facts["entries"].append({
            "logged": logged or "NO DATA",
            "session": _cell(raw, columns["session"]).strip() or "NO DATA",
            "symbol": symbol,
            "side": side,
            "entry_price": entry_match.group(1),
            "exit_time": _cell(raw, columns["filled"]).strip() if state == "CLOSED" else "",
            "exit_price": exit_match.group(1) if exit_match and state == "CLOSED" else "",
            "state": state,
            "later": later if state == "CLOSED" else "",
        })
    return facts


def render_cloud_status(now, alert_values: Sequence[Sequence], job_result: str | None = None) -> list[list]:
    """Status grid. Missing inputs stay NO DATA. Old inputs stay STALE."""
    observed = _naive_ist(now)
    job = str(job_result or "").strip().upper()
    if job not in ("PASS", "FAIL"):
        job = "NO DATA"
    facts = _overnight_facts(alert_values)
    entries = facts["entries"]
    if not entries:
        entry_count = "NO DATA"
        exit_count = "NO DATA"
        open_count = "NO DATA"
        freshness = "NO DATA"
        age = "NO DATA"
        last_data = "NO DATA"
    else:
        closed = [row for row in entries if row["state"] == "CLOSED"]
        open_rows = [row for row in entries if row["state"] != "CLOSED"]
        entry_count = len(entries)
        exit_count = len(closed)
        open_count = len(open_rows)
        last_data = facts["latest"].strftime("%Y-%m-%d %H:%M:%S") if facts["latest"] else "NO DATA"
        if facts["latest"] is None or observed is None:
            freshness = "NO DATA"
            age = "NO DATA"
        else:
            delta = observed - facts["latest"]
            if delta.total_seconds() < 0:
                delta = dt.timedelta(0)
            hours = int(delta.total_seconds() // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            age = f"{hours}h {minutes}m"
            freshness = "STALE" if delta > STALE_AFTER else "FRESH"
    last_run = observed.strftime("%Y-%m-%d %H:%M:%S") if observed else "NO DATA"
    rows = [
        ["CLOUD PAPER STATUS"],
        ["Counts overnight paper rows that already have an entry price. Exits require an option price and WIN, LOSS, or SCRATCH."],
        ["A futures percent in the later-change column is not an exit. Missing quotes stay NO DATA."],
        [],
        ["Last run time", last_run],
        ["Cloud job", job],
        ["Data time", last_data if entries else "NO DATA"],
        ["Data age", age],
        ["Freshness", freshness],
        ["Open paper positions", open_count],
        ["Paper entries", entry_count],
        ["Paper exits", exit_count],
        ["Broker orders", "DISABLED"],
        [],
        ["State", "Session date", "Symbol", "Side", "Entry time", "Entry price", "Exit time", "Exit price"],
    ]
    for item in entries:
        rows.append([
            item["state"],
            item["session"],
            item["symbol"],
            item["side"],
            item["logged"],
            item["entry_price"],
            item["exit_time"] or ("NO DATA" if item["state"] == "NO DATA" else ""),
            item["exit_price"] or ("NO DATA" if item["state"] != "CLOSED" else ""),
        ])
    return rows


def refresh_cloud_paper_view(sh, now, reconciled_results=None):
    """Write the CLOUD_STATUS tab and merge real ledger rows. Does not place orders."""
    values = []
    try:
        values = sh.worksheet("PAPER_ALERT_LOG").get_all_values()
    except Exception as exc:
        print(f"[WARN] PAPER_ALERT_LOG could not be read for cloud status: {exc}")
    rows = apply_exit_updates(
        ledger_rows_from_alerts(values, os.getenv("RUN_ID", "")),
        reconciled_results or [],
    )
    if rows:
        upsert_paper_ledger(default_ledger_path(), rows)
    status = render_cloud_status(now, values, job_result=None)
    from sheet_grid import write_grid
    try:
        worksheet = sh.worksheet("CLOUD_STATUS")
    except Exception:
        worksheet = sh.add_worksheet(title="CLOUD_STATUS", rows=str(max(80, len(status) + 5)), cols="8")
    write_grid(worksheet, status)
    print("[OK] CLOUD_STATUS written from the paper log")
    return status
