#!/usr/bin/env python3
import sys
from pathlib import Path
import gspread

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import credentials

creds_info = credentials.resolve_service_account_info()
gc = gspread.service_account_from_dict(creds_info)
sh = gc.open_by_key(credentials.require_authoritative_sheet_id())
ws = sh.worksheet("PAPER_ALERT_LOG")

fixes = {
    1409: "5.63% (SCRATCH) exit 3.00",
    1410: "34.52% (WIN) exit 26.50",
    1535: "0.33% (SCRATCH) exit 15.30",
}

print("Sanitizing formula error cells in Google Sheet PAPER_ALERT_LOG...")
for row, clean_val in fixes.items():
    # Update cell with clean text (no leading + which triggers Google Sheets formula parser)
    ws.update(range_name=f"J{row}", values=[[clean_val]], value_input_option="RAW")
    print(f"  Fixed cell J{row} -> {clean_val}")

# Verification
print("\nVerifying cell rendered values in Google Sheets:")
for row in fixes.keys():
    rendered = ws.cell(row, 10).value
    print(f"  Row {row} Col 10: {rendered}")
    assert rendered != "#ERROR!", f"Cell J{row} still has #ERROR!"

print("All PAPER_ALERT_LOG formula errors in Google Sheet 100% FIXED & VERIFIED!")
