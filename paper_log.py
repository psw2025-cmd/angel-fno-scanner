"""Paper-outcome sheet built only from PAPER_ALERT_LOG rows.

Stats stay blank until a later session has filled both an entry observation
and a later observation. This module does not create sample trades.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from gainers import as_float

PAPER_HEADERS = [
    "Logged at IST",
    "Session date",
    "Symbol",
    "Side",
    "Fut LTP",
    "Session change %",
    "CE contract",
    "PE contract",
    "Note",
    "Later session change %",
    "Outcome filled at",
]


def _index(header: Sequence[str], name: str) -> int | None:
    for index, cell in enumerate(header):
        if str(cell).strip().lower() == name.lower():
            return index
    return None


def _cell(row: Sequence, index: int | None):
    if index is None or index >= len(row):
        return ""
    return row[index]


def measured_outcomes(values: Sequence[Sequence]) -> list[dict]:
    """Return log rows that already contain a later session change filled by a previous run."""
    if not values:
        return []
    header = [str(cell) for cell in values[0]]
    needed = [
        "Logged at IST",
        "Session date",
        "Symbol",
        "Side",
        "Fut LTP",
        "Session change %",
        "Later session change %",
        "Outcome filled at",
    ]
    columns = {name: _index(header, name) for name in needed}
    if columns["Symbol"] is None or columns["Later session change %"] is None:
        return []
    outcomes = []
    for row in values[1:]:
        if not row or not str(_cell(row, columns["Symbol"])).strip():
            continue
        later = as_float(_cell(row, columns["Later session change %"]))
        entry = as_float(_cell(row, columns["Session change %"]))
        if later is None or entry is None:
            continue
        outcomes.append({
            "logged_at": str(_cell(row, columns["Logged at IST"])),
            "session_date": str(_cell(row, columns["Session date"])),
            "symbol": str(_cell(row, columns["Symbol"])).strip().upper(),
            "side": str(_cell(row, columns["Side"])).strip().upper(),
            "entry_change": entry,
            "later_change": later,
            "filled_at": str(_cell(row, columns["Outcome filled at"])),
        })
    return outcomes


def summarize_outcomes(outcomes: Sequence[dict]) -> dict:
    """Win rate uses the sign of the later futures change versus the logged side.

    A CE log wins when the later session change is higher than the entry change.
    A PE log wins when the later session change is lower. With no filled rows the
    rates stay None.
    """
    if not outcomes:
        return {
            "count": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": None,
            "average_follow_through": None,
        }
    wins = 0
    follow = []
    for outcome in outcomes:
        move = outcome["later_change"] - outcome["entry_change"]
        side = outcome["side"]
        if side in ("PE", "BUY_PE", "BEARISH"):
            move = -move
        follow.append(move)
        if move > 0:
            wins += 1
    losses = len(outcomes) - wins
    return {
        "count": len(outcomes),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / len(outcomes),
        "average_follow_through": sum(follow) / len(follow),
    }


def render_production_sheet(values: Sequence[Sequence], now: datetime) -> list[list]:
    outcomes = measured_outcomes(values)
    summary = summarize_outcomes(outcomes)
    win_rate = "" if summary["win_rate"] is None else round(summary["win_rate"], 4)
    follow = "" if summary["average_follow_through"] is None else round(summary["average_follow_through"], 4)
    rows = [
        ["MEASURED PAPER OUTCOMES"],
        [
            "Counts only PAPER_ALERT_LOG rows that already have a later session change. "
            "No sample trades are written. A blank win rate means no filled outcome yet."
        ],
        [],
        ["As of", now.strftime("%Y-%m-%d %H:%M:%S") + " IST"],
        ["Filled outcomes", summary["count"]],
        ["Wins", summary["wins"] if summary["count"] else ""],
        ["Losses", summary["losses"] if summary["count"] else ""],
        ["Win rate", win_rate],
        ["Average follow-through (percentage points)", follow],
        [],
        [
            "Logged at IST",
            "Session date",
            "Symbol",
            "Side",
            "Entry session change %",
            "Later session change %",
            "Follow-through",
            "Outcome filled at",
        ],
    ]
    for outcome in outcomes:
        move = outcome["later_change"] - outcome["entry_change"]
        if outcome["side"] in ("PE", "BUY_PE", "BEARISH"):
            move = -move
        rows.append([
            outcome["logged_at"],
            outcome["session_date"],
            outcome["symbol"],
            outcome["side"],
            outcome["entry_change"],
            outcome["later_change"],
            round(move, 4),
            outcome["filled_at"],
        ])
    return rows


def alerts_to_append(existing: Sequence[Sequence], signals: Sequence[dict], now: datetime, market_open: bool) -> list[list]:
    """New PAPER_ALERT_LOG rows for live signals. Closed sessions append nothing."""
    if not market_open or not signals:
        return []
    seen = set()
    if existing:
        header = [str(cell) for cell in existing[0]]
        columns = {
            "session": _index(header, "Session date"),
            "symbol": _index(header, "Symbol"),
            "side": _index(header, "Side"),
        }
        for row in existing[1:]:
            seen.add((
                str(_cell(row, columns["session"])).strip(),
                str(_cell(row, columns["symbol"])).strip().upper(),
                str(_cell(row, columns["side"])).strip().upper(),
            ))
    session_date = now.strftime("%Y-%m-%d")
    if hasattr(now, "tzinfo") and now.tzinfo is not None:
        from zoneinfo import ZoneInfo
        stamped = now.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
    else:
        stamped = now.strftime("%Y-%m-%d %H:%M:%S")
    fresh = []
    for signal in signals:
        symbol = str(signal.get("symbol") or "").strip().upper()
        side = str(signal.get("side") or "").strip().upper()
        if not symbol or side not in ("CE", "PE"):
            continue
        key = (session_date, symbol, side)
        if key in seen:
            continue
        seen.add(key)
        fresh.append([
            stamped,
            session_date,
            symbol,
            side,
            signal.get("fut_ltp", ""),
            signal.get("session_change", ""),
            signal.get("ce_contract", ""),
            signal.get("pe_contract", ""),
            "Logged from the live Angel quote. Outcome stays blank until a later session.",
            "",
            "",
        ])
    return fresh


def fill_later_changes(existing: Sequence[Sequence], latest: dict[str, float], now: datetime) -> list[list] | None:
    """Fill blank later-change cells from a newer session. Returns None when nothing changes."""
    if not existing:
        return None
    header = [str(cell) for cell in existing[0]]
    width = len(header)
    columns = {
        "session": _index(header, "Session date"),
        "symbol": _index(header, "Symbol"),
        "later": _index(header, "Later session change %"),
        "filled": _index(header, "Outcome filled at"),
    }
    if None in columns.values():
        return None
    today = now.strftime("%Y-%m-%d")
    if hasattr(now, "tzinfo") and now.tzinfo is not None:
        from zoneinfo import ZoneInfo
        stamped = now.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
    else:
        stamped = now.strftime("%Y-%m-%d %H:%M:%S")
    changed = False
    output = [list(header)]
    for row in existing[1:]:
        padded = list(row) + [""] * (width - len(row))
        padded = padded[:width]
        session = str(padded[columns["session"]]).strip()
        symbol = str(padded[columns["symbol"]]).strip().upper()
        later_blank = str(padded[columns["later"]]).strip() == ""
        if later_blank and session and session < today and symbol in latest:
            padded[columns["later"]] = latest[symbol]
            padded[columns["filled"]] = stamped
            changed = True
        if any(str(cell).strip() for cell in padded):
            output.append(padded)
    if not changed:
        return None
    return output
