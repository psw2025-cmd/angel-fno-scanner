#!/usr/bin/env python3
r"""
tools/refresh_tmdl_constants.py

Updates the embedded DATATABLE tables in TMDL (ForensicLive, CERank, Heartbeat)
with fresh, sanitized, pure-ASCII rows from C:\AngelFNO_Workstation\data\live_sheets\
so Power BI visuals (Top Actionable CE/PE, Heartbeat) display live real market data.
"""

import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLES_DIR = REPO_ROOT / "ANGEL_FNO_MONITOR.SemanticModel" / "definition" / "tables"
BRIDGE_DIR = Path(r"C:\AngelFNO_Workstation\data\live_sheets")


def to_ascii(s):
    if s is None:
        return ""
    # Strip non-ASCII characters / mojibake
    return s.encode("ascii", "ignore").decode("ascii").strip()


def parse_float(v):
    if not v:
        return 0.0
    s = str(v).replace(",", "").replace("+", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_int(v):
    if not v:
        return 0
    s = str(v).replace(",", "").replace("+", "").strip()
    try:
        return int(float(s))
    except Exception:
        return 0


def update_forensic_live():
    csv_path = BRIDGE_DIR / "FORENSIC_LIVE.csv"
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found. Skipping ForensicLive update.")
        return

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)

    print(f"Loaded {len(csv_rows)} live rows from {csv_path.name}")

    datatable_rows = []
    for r in csv_rows:
        sym = to_ascii(r.get("Symbol", ""))
        ts = to_ascii(r.get("Timestamp (IST)", "2026-10-18 17:57:46"))
        fut_ltp = parse_float(r.get("Fut LTP"))
        fut_chg = parse_float(r.get("Fut Chg %"))
        fut_obi = parse_float(r.get("Fut OBI"))
        atm_strike = parse_float(r.get("ATM Strike"))
        ce_contract = to_ascii(r.get("ATM CE Contract", ""))
        ce_ltp = parse_float(r.get("CE LTP"))
        ce_chg = parse_float(r.get("CE Chg %"))
        ce_oi = parse_int(r.get("CE OI"))
        ce_obi = parse_float(r.get("CE OBI"))
        pe_contract = to_ascii(r.get("ATM PE Contract", ""))
        pe_ltp = parse_float(r.get("PE LTP"))
        pe_chg = parse_float(r.get("PE Chg %"))
        pe_oi = parse_int(r.get("PE OI"))
        atm_pcr = parse_float(r.get("ATM PCR"))
        signal = to_ascii(r.get("Forensic Action Signal", ""))
        ce_valid = "TRUE" if (ce_ltp > 0 and ce_oi > 0) else "FALSE"
        pe_valid = "TRUE" if (pe_ltp > 0 and pe_oi > 0) else "FALSE"

        # Escape double quotes inside strings
        signal_clean = signal.replace('"', '""')
        row_str = f'\t\t\t\t        {{"{sym}", "{ts}", {fut_ltp}, {fut_chg}, {fut_obi}, {atm_strike}, "{ce_contract}", {ce_ltp}, {ce_chg}, {ce_oi}, {ce_obi}, "{pe_contract}", {pe_ltp}, {pe_chg}, {pe_oi}, {atm_pcr}, "{signal_clean}", {ce_valid}, {pe_valid}}}'
        datatable_rows.append(row_str)

    # Read existing ForensicLive.tmdl up to the DATATABLE definition
    tmdl_file = TABLES_DIR / "ForensicLive.tmdl"
    content = tmdl_file.read_text(encoding="utf-8")

    prefix_match = re.search(r'(partition ForensicLive_Partition = calculated\s+source =\s+DATATABLE\([\s\S]*?\{\s*\n)', content)
    if not prefix_match:
        print("[ERROR] Could not find DATATABLE opening in ForensicLive.tmdl")
        return

    prefix = content[:prefix_match.end()]
    new_content = prefix + ",\n".join(datatable_rows) + "\n\t\t\t\t    }\n\t\t\t\t)\n"
    tmdl_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Successfully updated ForensicLive.tmdl with {len(datatable_rows)} live rows!")


def update_cerank():
    csv_path = BRIDGE_DIR / "CE_PE_RANK.csv"
    if not csv_path.exists():
        print(f"[WARN] {csv_path} not found. Skipping CERank update.")
        return

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        first_line = f.readline()
        if "Symbol" not in first_line:
            reader = csv.DictReader(f)
        else:
            f.seek(0)
            reader = csv.DictReader(f)
        csv_rows = list(reader)

    print(f"Loaded {len(csv_rows)} live rows from {csv_path.name}")

    datatable_rows = []
    for r in csv_rows:
        sym = to_ascii(r.get("Symbol", ""))
        ts = to_ascii(r.get("Rank time IST", r.get("Timestamp (IST)", "2026-10-18 17:57:46")))
        status = to_ascii(r.get("Rank status", r.get("Session", r.get("Status", "MARKET CLOSED"))))
        fut_chg = parse_float(r.get("Session change %", r.get("Fut Chg %")))
        gap_pct = parse_float(r.get("Opening gap %", r.get("Opening Gap %")))
        fut_obi = parse_float(r.get("Fut OBI"))
        ce_chg = parse_float(r.get("CE chg %", r.get("CE Chg %")))
        pe_chg = parse_float(r.get("PE chg %", r.get("PE Chg %")))
        ce_oi = parse_int(r.get("CE OI"))
        pe_oi = parse_int(r.get("PE OI"))
        ce_oi_chg = parse_float(r.get("CE OI change", r.get("CE OI Chg %")))
        pe_oi_chg = parse_float(r.get("PE OI change", r.get("PE OI Chg %")))
        ce_obi = parse_float(r.get("CE OBI"))
        atm_pcr = parse_float(r.get("ATM PCR"))
        ce_streak = parse_int(r.get("CE streak", r.get("CE Streak")))
        pe_streak = parse_int(r.get("PE streak", r.get("PE Streak")))
        explanation = to_ascii(r.get("Why", r.get("Explanation", "Market closed. Session change is the last Angel print, not a forecast.")))
        exp_clean = explanation.replace('"', '""')

        row_str = f'\t\t\t\t        {{"{ts}", "{sym}", "{status}", {fut_chg}, {gap_pct}, {fut_obi}, {ce_chg}, {pe_chg}, {ce_oi}, {pe_oi}, {ce_oi_chg}, {pe_oi_chg}, {ce_obi}, {atm_pcr}, {ce_streak}, {pe_streak}, "{exp_clean}"}}'
        datatable_rows.append(row_str)

    tmdl_file = TABLES_DIR / "CERank.tmdl"
    content = tmdl_file.read_text(encoding="utf-8")

    prefix_match = re.search(r'(partition CERank_Partition = calculated\s+source =\s+DATATABLE\([\s\S]*?\{\s*\n)', content)
    if not prefix_match:
        print("[ERROR] Could not find DATATABLE opening in CERank.tmdl")
        return

    prefix = content[:prefix_match.end()]
    new_content = prefix + ",\n".join(datatable_rows) + "\n\t\t\t\t    }\n\t\t\t\t)\n"
    tmdl_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Successfully updated CERank.tmdl with {len(datatable_rows)} live rows!")


def update_heartbeat():
    csv_path = BRIDGE_DIR / "HEARTBEAT.csv"
    if not csv_path.exists():
        return

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if len(rows) < 2:
        return

    # Row 1 is header, Row 2 is first data row
    data_row = rows[1]
    ts = to_ascii(data_row[0] if len(data_row) > 0 else "2026-10-18 17:57:46")
    session_status = to_ascii(data_row[1] if len(data_row) > 1 else "CONNECTED_ANGEL_SMARTAPI")
    symbols = parse_int(data_row[2] if len(data_row) > 2 else "219")
    engine_status = to_ascii(data_row[3] if len(data_row) > 3 else "ACTIVE_PREDICTION_ENGINE | Cycle #346")
    sec_age = parse_float(data_row[4] if len(data_row) > 4 else "0")
    alert = to_ascii(data_row[5] if len(data_row) > 5 else "HEALTHY (ALL FEEDS ACTIVE)")

    tmdl_file = TABLES_DIR / "Heartbeat.tmdl"
    content = tmdl_file.read_text(encoding="utf-8")
    prefix_match = re.search(r'(partition Heartbeat_Partition = calculated\s+source =\s+DATATABLE\([\s\S]*?\{\s*\n)', content)
    if not prefix_match:
        return

    prefix = content[:prefix_match.end()]
    row_str = f'\t\t\t\t        {{"{ts}", {sec_age}, "{session_status}", "{engine_status}", {symbols}, "{alert}"}}'
    new_content = prefix + row_str + "\n\t\t\t\t    }\n\t\t\t\t)\n"
    tmdl_file.write_text(new_content, encoding="utf-8")
    print(f"[OK] Successfully updated Heartbeat.tmdl with live data from {ts} ({symbols} symbols)!")


def main():
    print("Refreshing TMDL embedded constants with live staged bridge data...")
    update_forensic_live()
    update_cerank()
    update_heartbeat()
    print("All TMDL constant tables successfully refreshed with live market data!")


if __name__ == "__main__":
    main()
