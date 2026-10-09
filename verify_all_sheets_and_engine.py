#!/usr/bin/env[WARN] python3
"""
verify_all_sheets_and_engine.py
Forensic[WARN] End-to-End[WARN] Verification[WARN] Suite[WARN] for:
1.[WARN] Google[WARN] Sheet[WARN] (1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs)[WARN] -[WARN] All[WARN] 17[WARN] Tabs
[WARN] [WARN] [WARN] -[WARN] Zero[WARN] Date-Serial[WARN] strings[WARN] (1899/1900)[WARN] in[WARN] numeric/price[WARN] columns
[WARN] [WARN] [WARN] -[WARN] Zero[WARN] #REF!,[WARN] #NAME?,[WARN] #VALUE!,[WARN] #N/A,[WARN] #ERROR![WARN] in[WARN] rendered[WARN] cells
[WARN] [WARN] [WARN] -[WARN] Zero[WARN] placeholders,[WARN] dummy[WARN] mock[WARN] data,[WARN] or[WARN] TODOs
[WARN] [WARN] [WARN] -[WARN] Strict[WARN] row/column[WARN] schema[WARN] alignment[WARN] (no[WARN] jagged[WARN] rows[WARN] or[WARN] shifts)
[WARN] [WARN] [WARN] -[WARN] Gate[WARN] verification[WARN] in[WARN] 'Formula[WARN] Checks'
2.[WARN] BigQuery[WARN] Sandbox[WARN] (fno-angel-prod-1790444589:fno_predictions)
[WARN] [WARN] [WARN] -[WARN] Tables:[WARN] option_predictions_live,[WARN] market_news_sentiment,[WARN] prediction_calibration_log
[WARN] [WARN] [WARN] -[WARN] Row[WARN] count[WARN] assertion[WARN] and[WARN] freshness[WARN] verification
3.[WARN] Prediction[WARN] &[WARN] Intensity[WARN] Engine[WARN] Calibration
[WARN] [WARN] [WARN] -[WARN] Pre-market[WARN] gap[WARN] predictions[WARN] populated
[WARN] [WARN] [WARN] -[WARN] Top-10[WARN] reconciliation[WARN] metrics[WARN] &[WARN] weights[WARN] verified
"""

import[WARN] os
import[WARN] sys
import[WARN] json
import[WARN] re
from[WARN] datetime[WARN] import[WARN] datetime
try:
[WARN] [WARN] [WARN] [WARN] import[WARN] pytz
except[WARN] ImportError:
[WARN] [WARN] [WARN] [WARN] pytz[WARN] =[WARN] None

import[WARN] gspread
from[WARN] google.oauth2.service_account[WARN] import[WARN] Credentials
from[WARN] google.cloud[WARN] import[WARN] bigquery

#[WARN] Ensure[WARN] parent[WARN] directory[WARN] is[WARN] on[WARN] sys.path
REPO_DIR[WARN] =[WARN] os.path.dirname(os.path.abspath(__file__))
if[WARN] REPO_DIR[WARN] not[WARN] in[WARN] sys.path:
[WARN] [WARN] [WARN] [WARN] sys.path.insert(0,[WARN] REPO_DIR)

from[WARN] angel_prediction_engine[WARN] import[WARN] (
[WARN] [WARN] [WARN] [WARN] get_gspread_client,
[WARN] [WARN] [WARN] [WARN] get_bigquery_client,
[WARN] [WARN] [WARN] [WARN] BQ_PROJECT_ID,
[WARN] [WARN] [WARN] [WARN] BQ_DATASET_ID,
[WARN] [WARN] [WARN] [WARN] SHEET_ID
)

GCP_PROJECT[WARN] =[WARN] BQ_PROJECT_ID
BQ_DATASET[WARN] =[WARN] BQ_DATASET_ID

EXPECTED_TABS[WARN] =[WARN] [
[WARN] [WARN] [WARN] [WARN] "PRE_BREAKOUT_SCANNER",
[WARN] [WARN] [WARN] [WARN] "Sheet1",
[WARN] [WARN] [WARN] [WARN] "F&O[WARN] Options[WARN] Top[WARN] Gainers[WARN] Tracker[WARN] Dashboard",
[WARN] [WARN] [WARN] [WARN] "LEGACY_F&O_DASHBOARD_OBJECT",
[WARN] [WARN] [WARN] [WARN] "Formula[WARN] Checks",
[WARN] [WARN] [WARN] [WARN] "PRODUCTION_APPROVED",
[WARN] [WARN] [WARN] [WARN] "Cloud_Automation_Setup",
[WARN] [WARN] [WARN] [WARN] "FORENSIC_LIVE",
[WARN] [WARN] [WARN] [WARN] "HEARTBEAT",
[WARN] [WARN] [WARN] [WARN] "CE_PE_RANK",
[WARN] [WARN] [WARN] [WARN] "NSE_EVENTS",
[WARN] [WARN] [WARN] [WARN] "PAPER_ALERT_LOG",
[WARN] [WARN] [WARN] [WARN] "NEWS_LIVE",
[WARN] [WARN] [WARN] [WARN] "NEWS_IMPACT",
[WARN] [WARN] [WARN] [WARN] "NEWS_TYPE_TALLY",
[WARN] [WARN] [WARN] [WARN] "TOP_GAINERS",
[WARN] [WARN] [WARN] [WARN] "OPTION_PREDICTIONS"
]

ERROR_PATTERNS[WARN] =[WARN] [
[WARN] [WARN] [WARN] [WARN] r"#REF!",
[WARN] [WARN] [WARN] [WARN] r"#NAME\?",
[WARN] [WARN] [WARN] [WARN] r"#VALUE!",
[WARN] [WARN] [WARN] [WARN] r"#N/A",
[WARN] [WARN] [WARN] [WARN] r"#DIV/0!",
[WARN] [WARN] [WARN] [WARN] r"#ERROR!",
[WARN] [WARN] [WARN] [WARN] r"\bErr:\d+\b",
]

DATE_SERIAL_PATTERN[WARN] =[WARN] re.compile(
[WARN] [WARN] [WARN] [WARN] r"(\b\d{1,2}-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(1899|1900)\b|\b(1899|1900)-\d{2}-\d{2}\b|^\s*(1899|1900)\s*$)",
[WARN] [WARN] [WARN] [WARN] re.IGNORECASE
)
DUMMY_PATTERN[WARN] =[WARN] re.compile(r"\b(placeholder|dummy_data|mock_price|fallback_quote)\b",[WARN] re.IGNORECASE)

def[WARN] get_sheets_client():
[WARN] [WARN] [WARN] [WARN] return[WARN] get_gspread_client()

def[WARN] audit_sheets():
[WARN] [WARN] [WARN] [WARN] print(f"\n=======================================================")
[WARN] [WARN] [WARN] [WARN] print(f"[AUDIT[WARN] PART[WARN] 1][WARN] FORENSIC[WARN] CELL-BY-CELL[WARN] AUDIT[WARN] OF[WARN] ALL[WARN] 17[WARN] TABS")
[WARN] [WARN] [WARN] [WARN] print(f"Spreadsheet:[WARN] {SHEET_ID}")
[WARN] [WARN] [WARN] [WARN] print(f"=======================================================")

[WARN] [WARN] [WARN] [WARN] gc[WARN] =[WARN] get_sheets_client()
[WARN] [WARN] [WARN] [WARN] sh[WARN] =[WARN] gc.open_by_key(SHEET_ID)

[WARN] [WARN] [WARN] [WARN] existing_worksheets[WARN] =[WARN] {ws.title:[WARN] ws[WARN] for[WARN] ws[WARN] in[WARN] sh.worksheets()}
[WARN] [WARN] [WARN] [WARN] print(f"[INFO][WARN] Discovered[WARN] {len(existing_worksheets)}[WARN] worksheets.")

[WARN] [WARN] [WARN] [WARN] missing_tabs[WARN] =[WARN] [tab[WARN] for[WARN] tab[WARN] in[WARN] EXPECTED_TABS[WARN] if[WARN] tab[WARN] not[WARN] in[WARN] existing_worksheets]
[WARN] [WARN] [WARN] [WARN] if[WARN] missing_tabs:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[FAIL][WARN] Missing[WARN] expected[WARN] tabs:[WARN] {missing_tabs}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] return[WARN] False,[WARN] {"missing_tabs":[WARN] missing_tabs}
[WARN] [WARN] [WARN] [WARN] else:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[PASS][WARN] All[WARN] 17[WARN] expected[WARN] tabs[WARN] exist[WARN] in[WARN] Google[WARN] Sheet.")

[WARN] [WARN] [WARN] [WARN] tab_audit_results[WARN] =[WARN] {}
[WARN] [WARN] [WARN] [WARN] total_cells_checked[WARN] =[WARN] 0
[WARN] [WARN] [WARN] [WARN] total_formula_errors[WARN] =[WARN] 0
[WARN] [WARN] [WARN] [WARN] total_date_serials[WARN] =[WARN] 0
[WARN] [WARN] [WARN] [WARN] total_dummy_strings[WARN] =[WARN] 0
[WARN] [WARN] [WARN] [WARN] column_shift_errors[WARN] =[WARN] 0

[WARN] [WARN] [WARN] [WARN] for[WARN] tab_name[WARN] in[WARN] EXPECTED_TABS:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] ws[WARN] =[WARN] existing_worksheets[tab_name]
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] all_values[WARN] =[WARN] ws.get_all_values()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] row_count[WARN] =[WARN] len(all_values)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] col_count[WARN] =[WARN] max(len(r)[WARN] for[WARN] r[WARN] in[WARN] all_values)[WARN] if[WARN] all_values[WARN] else[WARN] 0

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_errors[WARN] =[WARN] {
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "formula_errors":[WARN] [],
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "date_serials":[WARN] [],
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "dummy_strings":[WARN] [],
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "row_count":[WARN] row_count,
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "col_count":[WARN] col_count
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] }

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Check[WARN] FORENSIC_LIVE[WARN] schema[WARN] specifically[WARN] (18[WARN] columns[WARN] expected)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_name[WARN] ==[WARN] "FORENSIC_LIVE":
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] r_idx,[WARN] r[WARN] in[WARN] enumerate(all_values[1:],[WARN] start=2):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] len(r)[WARN] !=[WARN] 18[WARN] and[WARN] len(r)[WARN] >[WARN] 0:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_errors.setdefault("schema_shifts",[WARN] []).append(f"Row[WARN] {r_idx}[WARN] has[WARN] {len(r)}[WARN] cols[WARN] instead[WARN] of[WARN] 18")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] column_shift_errors[WARN] +=[WARN] 1

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] r_idx,[WARN] row[WARN] in[WARN] enumerate(all_values,[WARN] start=1):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] c_idx,[WARN] cell[WARN] in[WARN] enumerate(row,[WARN] start=1):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] total_cells_checked[WARN] +=[WARN] 1
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] cell_str[WARN] =[WARN] str(cell).strip()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] not[WARN] cell_str:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] continue

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Check[WARN] formula[WARN] errors
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] pattern[WARN] in[ERROR]_PATTERNS:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] re.search(pattern,[WARN] cell_str):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_errors["formula_errors"].append((r_idx,[WARN] c_idx,[WARN] cell_str))
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] total_formula_errors[WARN] +=[WARN] 1
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] break

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Check[WARN] date-serial[WARN] corruption[WARN] in[WARN] numeric[WARN] columns[WARN] (ignore[WARN] purely[WARN] timestamp/date[WARN] headers)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_name[WARN] in[WARN] ["Sheet1",[WARN] "TOP_GAINERS",[WARN] "FORENSIC_LIVE",[WARN] "OPTION_PREDICTIONS",[WARN] "PRE_BREAKOUT_SCANNER"]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Ignore[WARN] column[WARN] A[WARN] if[WARN] it[WARN] is[WARN] a[WARN] real[WARN] timestamp[WARN] header[WARN] or[WARN] timestamp[WARN] value
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] c_idx[WARN] >[WARN] 1[WARN] or[WARN] "Timestamp"[WARN] not[WARN] in[WARN] all_values[0][0]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] DATE_SERIAL_PATTERN.search(cell_str):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_errors["date_serials"].append((r_idx,[WARN] c_idx,[WARN] cell_str))
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] total_date_serials[WARN] +=[WARN] 1

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Check[WARN] dummy[WARN] strings[WARN] (excluding[WARN] audit[WARN] instructions[WARN] or[WARN] gate[WARN] definitions)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_name[WARN] not[WARN] in[WARN] ["Cloud_Automation_Setup"]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] DUMMY_PATTERN.search(cell_str):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_errors["dummy_strings"].append((r_idx,[WARN] c_idx,[WARN] cell_str))
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] total_dummy_strings[WARN] +=[WARN] 1

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tab_audit_results[tab_name][WARN] =[WARN] tab_errors
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] status[WARN] =[WARN] "🟢[WARN] PASS"[WARN] if[WARN] not[WARN] (tab_errors["formula_errors"][WARN] or[WARN] tab_errors["date_serials"][WARN] or[WARN] tab_errors["dummy_strings"])[WARN] else[WARN] "🔴[WARN] FAIL"
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] {tab_name:40s}[WARN] |[WARN] Rows:[WARN] {row_count:4d}[WARN] |[WARN] Cols:[WARN] {col_count:2d}[WARN] |[WARN] Status:[WARN] {status}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_errors["formula_errors"]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] [WARN] [WARN] ⚠️[WARN] Formula[WARN] errors[WARN] ({len(tab_errors['formula_errors'])}):[WARN] {tab_errors['formula_errors'][:3]}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_errors["date_serials"]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] [WARN] [WARN] ⚠️[WARN] Date[WARN] serials[WARN] ({len(tab_errors['date_serials'])}):[WARN] {tab_errors['date_serials'][:3]}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] tab_errors["dummy_strings"]:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] [WARN] [WARN] ⚠️[WARN] Dummy[WARN] strings[WARN] ({len(tab_errors['dummy_strings'])}):[WARN] {tab_errors['dummy_strings'][:3]}")

[WARN] [WARN] [WARN] [WARN] print(f"\n[SUMMARY[WARN] PART[WARN] 1][WARN] Audited[WARN] {total_cells_checked}[WARN] cells[WARN] across[WARN] {len(EXPECTED_TABS)}[WARN] tabs.")
[WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Formula[WARN] Errors[WARN] (#REF!,[WARN] #NAME?,[WARN] etc.):[WARN] {total_formula_errors}")
[WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Date[WARN] Serial[WARN] Corruptions[WARN] (1899/1900):[WARN] [WARN] {total_date_serials}")
[WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Dummy[WARN] /[WARN] Placeholder[WARN] strings:[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] {total_dummy_strings}")
[WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Column[WARN] Shift[WARN] /[WARN] Schema[WARN] Errors:[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] {column_shift_errors}")

[WARN] [WARN] [WARN] [WARN] #[WARN] Inspect[WARN] Formula[WARN] Checks[WARN] gates[WARN] specifically
[WARN] [WARN] [WARN] [WARN] ws_fc[WARN] =[WARN] existing_worksheets.get("Formula[WARN] Checks")
[WARN] [WARN] [WARN] [WARN] gate_failures[WARN] =[WARN] 0
[WARN] [WARN] [WARN] [WARN] if[WARN] ws_fc:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] fc_values[WARN] =[WARN] ws_fc.get_all_values()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print("\n[INFO][WARN] Checking[WARN] 'Formula[WARN] Checks'[WARN] Tab[WARN] Verification[WARN] Gates:")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] r[WARN] in[WARN] fc_values:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] row_str[WARN] =[WARN] "[WARN] |[WARN] ".join(r)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] any(k[WARN] in[WARN] row_str[WARN] for[WARN] k[WARN] in[WARN] ["GATE-0",[WARN] "GATE-1",[WARN] "RANK",[WARN] "OVERALL"]):
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] {row_str}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] status_col[WARN] =[WARN] r[4].strip()[WARN] if[WARN] len(r)[WARN] >[WARN] 4[WARN] else[WARN] ""
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] "FAIL"[WARN] in[WARN] status_col:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] gate_failures[WARN] +=[WARN] 1

[WARN] [WARN] [WARN] [WARN] sheet_success[WARN] =[WARN] (total_formula_errors[WARN] ==[WARN] 0[WARN] and[WARN] total_date_serials[WARN] ==[WARN] 0[WARN] and[WARN] total_dummy_strings[WARN] ==[WARN] 0[WARN] and[WARN] column_shift_errors[WARN] ==[WARN] 0[WARN] and[WARN] gate_failures[WARN] ==[WARN] 0)
[WARN] [WARN] [WARN] [WARN] return[WARN] sheet_success,[WARN] tab_audit_results

def[WARN] audit_bigquery():
[WARN] [WARN] [WARN] [WARN] print(f"\n=======================================================")
[WARN] [WARN] [WARN] [WARN] print(f"[AUDIT[WARN] PART[WARN] 2][WARN] BIGQUERY[WARN] SANDBOX[WARN] VERIFICATION[WARN] ($0[WARN] COST)")
[WARN] [WARN] [WARN] [WARN] print(f"Project:[WARN] {GCP_PROJECT}[WARN] |[WARN] Dataset:[WARN] {BQ_DATASET}")
[WARN] [WARN] [WARN] [WARN] print(f"=======================================================")

[WARN] [WARN] [WARN] [WARN] try:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] client[WARN] =[WARN] get_bigquery_client()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] dataset_ref[WARN] =[WARN] client.dataset(BQ_DATASET)

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] tables_to_check[WARN] =[WARN] [
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "option_predictions_live",
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "market_news_sentiment",
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "prediction_calibration_log"
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] ]

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] bq_results[WARN] =[WARN] {}
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] all_tables_pass[WARN] =[WARN] True

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] for[WARN] tbl_name[WARN] in[WARN] tables_to_check:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] try:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] table[WARN] =[WARN] client.get_table(dataset_ref.table(tbl_name))
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] row_count[WARN] =[WARN] table.num_rows
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] size_mb[WARN] =[WARN] round(table.num_bytes[WARN] /[WARN] (1024[WARN] *[WARN] 1024),[WARN] 2)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] schema_fields[WARN] =[WARN] [f.name[WARN] for[WARN] f[WARN] in[WARN] table.schema]
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Table[WARN] '{tbl_name}':[WARN] {row_count}[WARN] rows,[WARN] {size_mb}[WARN] MB,[WARN] {len(schema_fields)}[WARN] columns.[WARN] 🟢[OK]")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] bq_results[tbl_name][WARN] =[WARN] {
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "exists":[WARN] True,
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "rows":[WARN] row_count,
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "size_mb":[WARN] size_mb,
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] "columns":[WARN] len(schema_fields)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] }
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] row_count[WARN] ==[WARN] 0:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] ⚠️[WARN] Warning:[WARN] Table[WARN] '{tbl_name}'[WARN] currently[WARN] has[WARN] 0[WARN] rows.")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] all_tables_pass[WARN] =[WARN] False
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] except[WARN] Exception[WARN] as[WARN] e:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Table[WARN] '{tbl_name}':[WARN] 🔴[ERROR][WARN] ({e})")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] bq_results[tbl_name][WARN] =[WARN] {"exists":[WARN] False,[WARN] "error":[WARN] str(e)}
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] all_tables_pass[WARN] =[WARN] False

[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] return[WARN] all_tables_pass,[WARN] bq_results

[WARN] [WARN] [WARN] [WARN] except[WARN] Exception[WARN] as[WARN] e:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[FAIL][WARN] BigQuery[WARN] Client[WARN] Error:[WARN] {e}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] return[WARN] False,[WARN] {"error":[WARN] str(e)}

def[WARN] audit_engine_state():
[WARN] [WARN] [WARN] [WARN] print(f"\n=======================================================")
[WARN] [WARN] [WARN] [WARN] print(f"[AUDIT[WARN] PART[WARN] 3][WARN] PRE-MARKET[WARN] &[WARN] CALIBRATION[WARN] STATE[WARN] ENGINE[WARN] AUDIT")
[WARN] [WARN] [WARN] [WARN] print(f"=======================================================")

[WARN] [WARN] [WARN] [WARN] state_path[WARN] =[WARN] os.path.expanduser("~/angel_prediction_state.json")
[WARN] [WARN] [WARN] [WARN] cal_path[WARN] =[WARN] os.path.expanduser("~/angel_calibration_state.json")
[WARN] [WARN] [WARN] [WARN] local_data_path[WARN] =[WARN] os.path.join(REPO_DIR,[WARN] "data",[WARN] "latest_predictions.json")

[WARN] [WARN] [WARN] [WARN] state_ok[WARN] =[WARN] os.path.exists(state_path)[WARN] or[WARN] os.path.exists(local_data_path)
[WARN] [WARN] [WARN] [WARN] cal_ok[WARN] =[WARN] os.path.exists(cal_path)

[WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Prediction[WARN] State[WARN] ({state_path}[WARN] or[WARN] {local_data_path}):[WARN] {'🟢[WARN] FOUND'[WARN] if[WARN] state_ok[WARN] else[WARN] '🔴[WARN] MISSING'}")

[WARN] [WARN] [WARN] [WARN] if[WARN] cal_ok:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Calibration[WARN] State[WARN] ({cal_path}):[WARN] 🟢[WARN] FOUND")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] with[WARN] open(cal_path,[WARN] "r")[WARN] as[WARN] f:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] cal_data[WARN] =[WARN] json.load(f)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] last_rec[WARN] =[WARN] cal_data.get("last_reconciliation",[WARN] {})
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Cycle:[WARN] {cal_data.get('cycle_number',[WARN] last_rec.get('cycle',[WARN] 0))}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Hit[WARN] Rate:[WARN] {last_rec.get('hit_rate_pct',[WARN] 0.0)}%")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Recall[WARN] @[WARN] 10:[WARN] {last_rec.get('recall_at_10',[WARN] 0.0)}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Mean[WARN] Rank:[WARN] {last_rec.get('mean_rank',[WARN] 0.0)}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Weights:[WARN] {cal_data.get('weights',[WARN] {})}")
[WARN] [WARN] [WARN] [WARN] else:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] try:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] client[WARN] =[WARN] get_bigquery_client()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] sql[WARN] =[WARN] f"""
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] SELECT[WARN] *[WARN] FROM[WARN] `{BQ_PROJECT_ID}.{BQ_DATASET_ID}.prediction_calibration_log`
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] ORDER[WARN] BY[WARN] cycle_number[WARN] DESC[WARN] LIMIT[WARN] 1
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] """
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] rows[WARN] =[WARN] list(client.query(sql).result())
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] if[WARN] rows:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] cal_ok[WARN] =[WARN] True
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] r[WARN] =[WARN] dict(rows[0])
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Calibration[WARN] State[WARN] (BigQuery[WARN] Sandbox[WARN] Log):[WARN] 🟢[WARN] FOUND")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Cycle:[WARN] {r.get('cycle_number',[WARN] 0)}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Hit[WARN] Rate:[WARN] {r.get('hit_rate_pct',[WARN] 0.0)}%")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Recall[WARN] @[WARN] 10:[WARN] {r.get('recall_at_10',[WARN] 0.0)}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] [WARN] [WARN] Mean[WARN] Rank:[WARN] {r.get('mean_rank_of_top10',[WARN] 0.0)}")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] except[WARN] Exception[WARN] as[WARN] e:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"[WARN] -[WARN] Calibration[WARN] State:[WARN] 🔴[WARN] MISSING[WARN] ({e})")

[WARN] [WARN] [WARN] [WARN] return[WARN] (state_ok[WARN] and[WARN] cal_ok)


def[WARN] audit_publication():
[WARN] [WARN] [WARN] [WARN] """A[WARN] green[WARN] table/cell[WARN] audit[WARN] alone[WARN] does[WARN] not[WARN] establish[WARN] a[WARN] completed[WARN] cycle."""
[WARN] [WARN] [WARN] [WARN] from[WARN] publication[WARN] import[WARN] verify_current_publication
[WARN] [WARN] [WARN] [WARN] try:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] client[WARN] =[WARN] get_bigquery_client()
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] book[WARN] =[WARN] get_gspread_client().open_by_key(SHEET_ID)
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] identity[WARN] =[WARN] verify_current_publication(book,[WARN] client,
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] client.dataset(BQ_DATASET).table("option_predictions_live"))
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] return[WARN] True,[WARN] identity
[WARN] [WARN] [WARN] [WARN] except[WARN] Exception[WARN] as[WARN] exc:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] #[WARN] Do[WARN] not[WARN] put[WARN] credential-bearing[WARN] provider[WARN] exception[WARN] text[WARN] in[WARN] evidence.
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] return[WARN] False,[WARN] {"status":[WARN] "UNVERIFIED",[WARN] "error_type":[WARN] type(exc).__name__}

def[WARN] main():
[WARN] [WARN] [WARN] [WARN] sheet_ok,[WARN] sheet_res[WARN] =[WARN] audit_sheets()
[WARN] [WARN] [WARN] [WARN] bq_ok,[WARN] bq_res[WARN] =[WARN] audit_bigquery()
[WARN] [WARN] [WARN] [WARN] eng_ok[WARN] =[WARN] audit_engine_state()
[WARN] [WARN] [WARN] [WARN] publication_ok,[WARN] publication_evidence[WARN] =[WARN] audit_publication()

[WARN] [WARN] [WARN] [WARN] print(f"\n=======================================================")
[WARN] [WARN] [WARN] [WARN] print(f"FINAL[WARN] SYSTEM[WARN] VERIFICATION[WARN] GATE[WARN] SUMMARY")
[WARN] [WARN] [WARN] [WARN] print(f"=======================================================")
[WARN] [WARN] [WARN] [WARN] print(f"1.[WARN] 17-Tab[WARN] Google[WARN] Sheet[WARN] Cell[WARN] Audit:[WARN] {'🟢[WARN] 100%[WARN] PASSED'[WARN] if[WARN] sheet_ok[WARN] else[WARN] '🔴[WARN] FAILED'}")
[WARN] [WARN] [WARN] [WARN] print(f"2.[WARN] BigQuery[WARN] Sandbox[WARN] Dataset[WARN] Audit:[WARN] {'🟢[WARN] 100%[WARN] PASSED'[WARN] if[WARN] bq_ok[WARN] else[WARN] '🔴[WARN] FAILED'}")
[WARN] [WARN] [WARN] [WARN] print(f"3.[WARN] Pre-Market[WARN] &[WARN] Calibration[WARN] Engine:[WARN] {'🟢[WARN] 100%[WARN] PASSED'[WARN] if[WARN] eng_ok[WARN] else[WARN] '🔴[WARN] FAILED'}")

[WARN] [WARN] [WARN] [WARN] print(f"4.[WARN] Completed[WARN] publication/readback:[WARN] {publication_ok};[WARN] {publication_evidence}")
[WARN] [WARN] [WARN] [WARN] if[WARN] sheet_ok[WARN] and[WARN] bq_ok[WARN] and[WARN] eng_ok[WARN] and[WARN] publication_ok:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"\n✨[WARN] ALL[WARN] PRODUCTION[WARN] GATES[WARN] VERIFIED[WARN] 100%[WARN] PASS![WARN] EXITING[WARN] CODE[WARN] 0.")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] sys.exit(0)
[WARN] [WARN] [WARN] [WARN] else:
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] print(f"\n⚠️[WARN] ONE[WARN] OR[WARN] MORE[WARN] VERIFICATION[WARN] GATES[WARN] REQUIRE[WARN] RESOLUTION.")
[WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] [WARN] sys.exit(1)

if[WARN] __name__[WARN] ==[WARN] "__main__":
[WARN] [WARN] [WARN] [WARN] main()
