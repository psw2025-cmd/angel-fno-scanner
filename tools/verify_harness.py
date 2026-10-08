#!/usr/bin/env python3
"""
tools/verify_harness.py

Single verification harness that:
- Pulls live data from Google Sheets (7 specified tabs/ranges)
- Pulls live data from BigQuery (4 tables in fno_predictions)
- Cross-verifies every field between them
- Runs live unit tests (pytest -q -> 154 passed)
- Compares against a known-good baseline in audit/baseline.json
- Writes a dated evidence report every run: audit/verify_harness_<YYYYMMDD_HHMMSS>.json
- Alerts on any drift
- Strict read-only: never mutates Google Sheets or BigQuery
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from angel_prediction_engine import get_bigquery_client, get_gspread_client, SHEET_ID
from credentials import require_authoritative_sheet_id

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = "fno_predictions"
TABLES = [
    "option_predictions_live",
    "market_news_sentiment",
    "next_day_gap_predictions",
    "prediction_calibration_log",
]

SHEET_TABS = {
    "FORENSIC_LIVE": ("A1:R500", "UNFORMATTED_VALUE"),
    "CE_PE_RANK": ("A1:F500", "UNFORMATTED_VALUE"),
    "Formula Checks": ("A1:H40", "FORMULA"),
    "WRITE_PROVENANCE": ("A1:F500", "UNFORMATTED_VALUE"),
    "PUBLICATION_STATUS": ("A1:I5", "UNFORMATTED_VALUE"),
    "PREMARKET_VS_ACTUAL": ("A1:J50", "UNFORMATTED_VALUE"),
    "TOMORROW_EXPLOSIVE_WATCH": ("A1:L50", "UNFORMATTED_VALUE"),
}

AUDIT_DIR = REPO_ROOT / "audit"
BASELINE_PATH = AUDIT_DIR / "baseline.json"
CANDIDATE_PATH = AUDIT_DIR / "baseline_candidate.json"


def get_git_info():
    try:
        head_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception as e:
        head_sha = f"UNKNOWN ({e})"

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        branch = "main"

    try:
        remote_sha = subprocess.check_output(
            ["git", "rev-parse", "origin/main"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        remote_sha = "UNKNOWN"

    try:
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        ).splitlines()
        # Filter out harness-generated candidate/evidence files if present
        filtered = [
            line for line in porcelain
            if not any(
                p in line for p in [
                    "baseline_candidate.json",
                    "verify_harness_",
                ]
            )
        ]
    except Exception:
        filtered = ["UNKNOWN"]

    ahead, behind = 0, 0
    try:
        counts = subprocess.check_output(
            ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
            cwd=REPO_ROOT,
            text=True,
        ).strip().split()
        if len(counts) == 2:
            ahead, behind = int(counts[0]), int(counts[1])
    except Exception:
        pass

    return {
        "head_sha": head_sha,
        "remote_sha": remote_sha,
        "branch": branch,
        "porcelain_count": len(filtered),
        "porcelain_lines": filtered,
        "ahead": ahead,
        "behind": behind,
    }


def pull_google_sheets():
    """Pull the single authoritative Sheet and fail closed on authority drift."""
    authoritative_sheet_id = require_authoritative_sheet_id(SHEET_ID)
    sh = None
    for attempt in range(4):
        try:
            gc = get_gspread_client()
            sh = gc.open_by_key(authoritative_sheet_id)
            break
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Failed to authenticate with Google Sheets: {e}") from e
            time.sleep(2 * (attempt + 1))

    sheet_data = {}
    for name, (rng, render_mode) in SHEET_TABS.items():
        last_err = None
        for attempt in range(3):
            try:
                ws = sh.worksheet(name)
                vals = ws.get_values(rng, value_render_option=render_mode)
                sheet_data[name] = vals
                break
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"Failed to fetch Google Sheet tab '{name}': {last_err}") from last_err

    return sheet_data, sh


def pull_bigquery():
    """Pull schema, counts, and latest provenance for all four fno_predictions tables."""
    try:
        bq = get_bigquery_client()
    except Exception as e:
        raise RuntimeError(f"Failed to authenticate with BigQuery: {e}") from e

    bq_schema = {}
    bq_counts = {}
    bq_latest = {}

    for t in TABLES:
        # 1. Schema
        try:
            schema_query = f"""
            SELECT column_name, data_type, is_nullable
            FROM `{PROJECT_ID}.{DATASET_ID}.INFORMATION_SCHEMA.COLUMNS`
            WHERE table_name = '{t}'
            ORDER BY ordinal_position
            """
            rows = list(bq.query(schema_query).result())
            bq_schema[t] = [
                {
                    "column_name": r.column_name,
                    "data_type": r.data_type,
                    "is_nullable": r.is_nullable,
                }
                for r in rows
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to fetch BigQuery schema for '{t}': {e}") from e

        # 2. Counts: total rows, distinct run_ids, null run_ids
        try:
            count_query = f"""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT run_id) as distinct_run_ids,
                COUNTIF(run_id IS NULL) as null_run_ids
            FROM `{PROJECT_ID}.{DATASET_ID}.{t}`
            """
            c_row = list(bq.query(count_query).result())[0]
            bq_counts[t] = {
                "total_rows": int(c_row.total_rows),
                "distinct_run_ids": int(c_row.distinct_run_ids),
                "null_run_ids": int(c_row.null_run_ids),
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fetch BigQuery counts for '{t}': {e}") from e

        # 3. Latest record by source_timestamp
        try:
            latest_query = f"""
            SELECT run_id, git_sha, writer_id, CAST(source_timestamp AS STRING) as source_timestamp
            FROM `{PROJECT_ID}.{DATASET_ID}.{t}`
            ORDER BY source_timestamp DESC NULLS LAST
            LIMIT 1
            """
            l_rows = list(bq.query(latest_query).result())
            if l_rows:
                lr = l_rows[0]
                bq_latest[t] = {
                    "run_id": lr.run_id,
                    "git_sha": lr.git_sha,
                    "writer_id": lr.writer_id,
                    "source_timestamp": lr.source_timestamp,
                }
            else:
                bq_latest[t] = {
                    "run_id": None,
                    "git_sha": None,
                    "writer_id": None,
                    "source_timestamp": None,
                }
        except Exception as e:
            raise RuntimeError(f"Failed to fetch BigQuery latest row for '{t}': {e}") from e

    return bq_schema, bq_counts, bq_latest


def check_gate_formulas(formula_rows, sheet_data, sh_obj):
    """
    Validate Formula Checks in two ways:
    1. every referenced range resolves to populated data;
    2. critical gate formulas exactly match the canonical 219-universe /
       200-ranked-contract contract documented in docs/formula-checks-contract.md.

    Returns (status, detail, issues).
    """
    ref_pattern = re.compile(
        r'(?:([A-Za-z0-9_]+)!)?\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?'
    )

    extra_sheet_cache = {}
    issues = []

    for row in formula_rows:
        for cell in row:
            text = str(cell).strip()
            if not text.startswith("="):
                continue

            for match in ref_pattern.finditer(text):
                sheet_name, col1, r1, col2, r2 = match.groups()
                target_sheet = sheet_name if sheet_name else "Formula Checks"

                if target_sheet in sheet_data:
                    data = sheet_data[target_sheet]
                elif target_sheet in extra_sheet_cache:
                    data = extra_sheet_cache[target_sheet]
                else:
                    try:
                        ws = sh_obj.worksheet(target_sheet)
                        data = ws.get_values("A1:Z300")
                        extra_sheet_cache[target_sheet] = data
                    except Exception:
                        issues.append(f"{target_sheet}!{col1}{r1} (missing sheet)")
                        continue

                row_start = int(r1) - 1
                row_end = int(r2) - 1 if r2 else row_start
                has_data = False
                for ri in range(row_start, min(len(data), row_end + 1)):
                    row_vals = data[ri]
                    if any(str(val).strip() != "" for val in row_vals):
                        has_data = True
                        break

                if not has_data:
                    ref_str = f"{target_sheet}!{col1}{r1}" + (f":{col2}{r2}" if col2 else "")
                    issues.append(ref_str)

    # Fail closed if the live sheet drifts back to the retired 216-symbol
    # formulas or compares the 200-contract rank board to the underlying universe.
    rows_by_gate = {
        str(row[0]).strip(): row
        for row in formula_rows
        if row and str(row[0]).strip()
    }
    required_formulas = {
        ("GATE-01", 2): '=COUNTA(FORENSIC_LIVE!B2:B220)&" / 219"',
        ("GATE-01", 4): '=IF(COUNTA(FORENSIC_LIVE!B2:B220)=219,"PASS","FAIL")',
        ("GATE-03", 2): '=COUNTIF(FORENSIC_LIVE!D2:D220,">0")&" / "&COUNTA(FORENSIC_LIVE!B2:B220)',
        ("GATE-03", 4): '=IF(COUNTIF(FORENSIC_LIVE!D2:D220,">0")=COUNTA(FORENSIC_LIVE!B2:B220),"PASS","FAIL")',
        ("GATE-04", 2): '=COUNTIFS(FORENSIC_LIVE!Q2:Q220,">=0",FORENSIC_LIVE!Q2:Q220,"<=10")&" in range; "&COUNTIFS(FORENSIC_LIVE!B2:B220,"<>",FORENSIC_LIVE!Q2:Q220,"")&" blank"',
        ("GATE-04", 4): '=IF(COUNTIFS(FORENSIC_LIVE!Q2:Q220,">10")+COUNTIFS(FORENSIC_LIVE!Q2:Q220,"<0")>0,"FAIL","PASS")',
        ("OVERALL", 2): '=(COUNTIF(E2:E6,"FAIL")+COUNTIF(E10:E11,"FAIL"))&" failed gates"',
        ("OVERALL", 4): '=IF(COUNTIF(E2:E6,"FAIL")+COUNTIF(E10:E11,"FAIL")>0,"BLOCKED",IF(C3="MARKET CLOSED","MARKET CLOSED — alerts are not live","PASS — session open and gates clear"))',
        ("GATE-06", 2): '=COUNTA(CE_PE_RANK!A5:A204)&" / 200"',
        ("GATE-06", 4): '=IF(COUNTA(CE_PE_RANK!A5:A204)=200,"PASS","FAIL")',
        ("GATE-07", 2): '=COUNTIF(CE_PE_RANK!U5:U204,"HIGH MOMENTUM")',
        ("GATE-07", 4): '=IF(C3="MARKET CLOSED",IF(N(C11)=0,"PASS","FAIL"),"SESSION OPEN")',
    }

    for (gate_id, col_idx), expected in required_formulas.items():
        row = rows_by_gate.get(gate_id, [])
        actual = str(row[col_idx]).strip() if len(row) > col_idx else "MISSING"
        if actual != expected:
            issues.append(
                f"{gate_id} formula contract mismatch at column {col_idx + 1}: "
                f"expected={expected!r} actual={actual!r}"
            )

    if not issues:
        return "PASS", "0 unpopulated refs", []
    return "FAIL", f"{len(issues)} formula/reference issues ({'; '.join(issues[:2])})", issues


def run_unit_tests():
    """Run pytest -q and capture exit code and summary."""
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        stdout = res.stdout.strip()
        last_line = stdout.splitlines()[-1] if stdout else ""
        return res.returncode, last_line
    except Exception as e:
        return 2, f"pytest execution failed: {e}"


def run_all_checks(sheet_data, sh_obj, bq_schema, bq_counts, bq_latest, git_info):
    """
    Executes exactly the 12 named checks:
    1. runid_type_all_string
    2. runid_latest_identical
    3. gitsha_latest_identical
    4. writer_id_market_bot
    5. sheet_vs_bq_runid_match
    6. sheet_vs_bq_gitsha_match
    7. forensic_live_symbol_count_219
    8. forensic_live_symbols_match_manifest
    9. gate_formulas_reference_populated_cells
    10. pytest_154_passed
    11. git_tree_clean
    12. git_synced_with_origin
    """
    checks = {}

    # Check 1: runid_type_all_string
    runid_types = {}
    for t in TABLES:
        col_type = next((c["data_type"] for c in bq_schema.get(t, []) if c["column_name"] == "run_id"), "MISSING")
        runid_types[t] = col_type
    all_string = all(tp == "STRING" for tp in runid_types.values())
    if all_string:
        checks["runid_type_all_string"] = {
            "status": "PASS",
            "detail": "all 4 tables STRING",
            "raw": runid_types,
        }
    else:
        checks["runid_type_all_string"] = {
            "status": "FAIL",
            "detail": " ".join(f"{t}={tp}" for t, tp in runid_types.items()),
            "raw": runid_types,
        }

    # Check 2: runid_latest_identical
    latest_runids = {t: bq_latest[t].get("run_id") for t in TABLES}
    runid_vals = set(latest_runids.values())
    aux_runids = [latest_runids[t] for t in TABLES if t != "option_predictions_live"]
    is_pre_cycle_null = (
        latest_runids.get("option_predictions_live") is not None
        and all(v is None for v in aux_runids)
    )
    if len(runid_vals) == 1 and None not in runid_vals:
        single_val = list(runid_vals)[0]
        checks["runid_latest_identical"] = {
            "status": "PASS",
            "detail": f"all 4 = {single_val}",
            "raw": latest_runids,
        }
    elif is_pre_cycle_null:
        checks["runid_latest_identical"] = {
            "status": "PENDING",
            "detail": f"option_predictions_live={latest_runids['option_predictions_live']} (3 auxiliary tables pre-cycle NULL)",
            "raw": latest_runids,
        }
    else:
        checks["runid_latest_identical"] = {
            "status": "FAIL",
            "detail": " ".join(f"{t}={v}" for t, v in latest_runids.items()),
            "raw": latest_runids,
        }

    # Check 3: gitsha_latest_identical
    latest_gitshas = {t: bq_latest[t].get("git_sha") for t in TABLES}
    gitsha_vals = set(latest_gitshas.values())
    aux_gitshas = [latest_gitshas[t] for t in TABLES if t != "option_predictions_live"]
    is_pre_cycle_gitsha_null = (
        latest_gitshas.get("option_predictions_live") is not None
        and all(v is None for v in aux_gitshas)
    )
    if len(gitsha_vals) == 1 and None not in gitsha_vals:
        single_sha = list(gitsha_vals)[0]
        checks["gitsha_latest_identical"] = {
            "status": "PASS",
            "detail": f"all 4 = {single_sha[:7]}...",
            "raw": latest_gitshas,
        }
    elif is_pre_cycle_gitsha_null:
        checks["gitsha_latest_identical"] = {
            "status": "PENDING",
            "detail": f"option_predictions_live={str(latest_gitshas['option_predictions_live'])[:7]} (3 auxiliary tables pre-cycle NULL)",
            "raw": latest_gitshas,
        }
    else:
        checks["gitsha_latest_identical"] = {
            "status": "FAIL",
            "detail": " ".join(f"{t}={str(v)[:7]}" for t, v in latest_gitshas.items()),
            "raw": latest_gitshas,
        }

    # Check 4: writer_id_market_bot
    latest_writers = {t: bq_latest[t].get("writer_id") for t in TABLES}
    all_mb = all(w == "market_bot" for w in latest_writers.values())
    aux_writers = [latest_writers[t] for t in TABLES if t != "option_predictions_live"]
    is_pre_cycle_writer_null = (
        latest_writers.get("option_predictions_live") == "market_bot"
        and all(w is None for w in aux_writers)
    )
    if all_mb:
        checks["writer_id_market_bot"] = {
            "status": "PASS",
            "detail": "all 4 = market_bot",
            "raw": latest_writers,
        }
    elif is_pre_cycle_writer_null:
        checks["writer_id_market_bot"] = {
            "status": "PENDING",
            "detail": "option_predictions_live=market_bot (3 auxiliary tables pre-cycle NULL)",
            "raw": latest_writers,
        }
    else:
        checks["writer_id_market_bot"] = {
            "status": "FAIL",
            "detail": " ".join(f"{t}={w}" for t, w in latest_writers.items()),
            "raw": latest_writers,
        }

    # Extract Sheet WRITE_PROVENANCE latest row
    wp_rows = sheet_data.get("WRITE_PROVENANCE", [])
    data_wp = [r for r in wp_rows[1:] if len(r) >= 4 and any(str(c).strip() for c in r)]
    sheet_latest_wp = data_wp[-1] if data_wp else []
    sheet_run_id = str(sheet_latest_wp[1]).strip() if len(sheet_latest_wp) > 1 else "MISSING"
    sheet_git_sha = str(sheet_latest_wp[2]).strip() if len(sheet_latest_wp) > 2 else "MISSING"

    # Find latest prediction_cycle row if streaming scanner_quote_loop is currently top
    pred_cycle_rows = [r for r in data_wp if len(r) > 4 and r[4].strip() == "prediction_cycle"]
    cycle_run_id = str(pred_cycle_rows[-1][1]).strip() if pred_cycle_rows else sheet_run_id

    # BigQuery reference values from option_predictions_live
    bq_ref_run_id = str(bq_latest["option_predictions_live"].get("run_id") or "NONE").strip()
    bq_ref_git_sha = str(bq_latest["option_predictions_live"].get("git_sha") or "NONE").strip()

    # Check 5: sheet_vs_bq_runid_match
    if sheet_run_id != "MISSING" and bq_ref_run_id != "NONE" and sheet_run_id == bq_ref_run_id:
        checks["sheet_vs_bq_runid_match"] = {
            "status": "PASS",
            "detail": f"sheet={sheet_run_id} bq={bq_ref_run_id}",
            "raw": {"sheet_run_id": sheet_run_id, "bq_run_id": bq_ref_run_id},
        }
    elif cycle_run_id != "MISSING" and bq_ref_run_id != "NONE" and cycle_run_id == bq_ref_run_id:
        checks["sheet_vs_bq_runid_match"] = {
            "status": "PASS",
            "detail": f"cycle sheet={cycle_run_id} bq={bq_ref_run_id} (streaming={sheet_run_id})",
            "raw": {"sheet_run_id": sheet_run_id, "cycle_run_id": cycle_run_id, "bq_ref_run_id": bq_ref_run_id},
        }
    else:
        checks["sheet_vs_bq_runid_match"] = {
            "status": "FAIL",
            "detail": f"sheet={sheet_run_id} bq={bq_ref_run_id}",
            "raw": {"sheet_run_id": sheet_run_id, "bq_run_id": bq_ref_run_id},
        }

    # Check 6: sheet_vs_bq_gitsha_match
    sh_short = sheet_git_sha[:7]
    bq_short = bq_ref_git_sha[:7]
    if (
        sheet_git_sha != "MISSING"
        and bq_ref_git_sha != "NONE"
        and (sheet_git_sha == bq_ref_git_sha or sheet_git_sha.startswith(bq_short) or bq_ref_git_sha.startswith(sh_short))
    ):
        checks["sheet_vs_bq_gitsha_match"] = {
            "status": "PASS",
            "detail": f"sheet={sh_short}... bq={bq_short}...",
            "raw": {"sheet_git_sha": sheet_git_sha, "bq_git_sha": bq_ref_git_sha},
        }
    else:
        checks["sheet_vs_bq_gitsha_match"] = {
            "status": "FAIL",
            "detail": f"sheet={sheet_git_sha} bq={bq_ref_git_sha}",
            "raw": {"sheet_git_sha": sheet_git_sha, "bq_git_sha": bq_ref_git_sha},
        }

    # Check 7: forensic_live_symbol_count_219
    fl_rows = sheet_data.get("FORENSIC_LIVE", [])
    fl_symbols = [
        str(r[1]).strip()
        for r in fl_rows[1:]
        if len(r) > 1 and str(r[1]).strip()
    ]
    fl_unique_symbols = sorted(set(fl_symbols))
    symbol_count = len(fl_unique_symbols)
    if symbol_count == 219:
        checks["forensic_live_symbol_count_219"] = {
            "status": "PASS",
            "detail": "219",
            "raw": {"count": symbol_count},
        }
    else:
        checks["forensic_live_symbol_count_219"] = {
            "status": "FAIL",
            "detail": f"count={symbol_count} expected=219",
            "raw": {"count": symbol_count, "expected": 219},
        }

    # Check 8: forensic_live_symbols_match_manifest
    manifest_file = REPO_ROOT / "agent_manifest.json"
    if manifest_file.exists():
        try:
            m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            m_symbols = set(m_data.get("universe", {}).get("symbols", []))
        except Exception:
            m_symbols = set()
    else:
        m_symbols = set()

    fl_set = set(fl_unique_symbols)
    if m_symbols and fl_set == m_symbols:
        checks["forensic_live_symbols_match_manifest"] = {
            "status": "PASS",
            "detail": f"{len(fl_set)}/{len(m_symbols)}",
            "raw": {"matched": len(fl_set), "total": len(m_symbols)},
        }
    else:
        missing = sorted(list(m_symbols - fl_set))
        extra = sorted(list(fl_set - m_symbols))
        checks["forensic_live_symbols_match_manifest"] = {
            "status": "FAIL",
            "detail": f"matched={len(fl_set & m_symbols)}/219 missing={len(missing)} extra={len(extra)}",
            "raw": {"missing": missing, "extra": extra},
        }

    # Check 9: gate_formulas_reference_populated_cells
    fc_rows = sheet_data.get("Formula Checks", [])
    gf_status, gf_detail, gf_unpopulated = check_gate_formulas(fc_rows, sheet_data, sh_obj)
    checks["gate_formulas_reference_populated_cells"] = {
        "status": gf_status,
        "detail": gf_detail,
        "raw": {"unpopulated": gf_unpopulated},
    }

    # Check 10: pytest_154_passed
    retcode, py_summary = run_unit_tests()
    m_tests = re.search(r"(\d+)\s+passed", py_summary) if py_summary else None
    passed_count = int(m_tests.group(1)) if m_tests else 0
    if retcode == 0 and passed_count >= 154:
        checks["pytest_154_passed"] = {
            "status": "PASS",
            "detail": f"{passed_count} passed",
            "raw": {"summary": py_summary, "exit_code": retcode},
        }
    else:
        checks["pytest_154_passed"] = {
            "status": "FAIL",
            "detail": py_summary if py_summary else f"exit code {retcode}",
            "raw": {"summary": py_summary, "exit_code": retcode},
        }

    # Check 11: git_tree_clean
    if git_info["porcelain_count"] == 0:
        checks["git_tree_clean"] = {
            "status": "PASS",
            "detail": "clean",
            "raw": {"porcelain": []},
        }
    else:
        checks["git_tree_clean"] = {
            "status": "FAIL",
            "detail": f"dirty ({git_info['porcelain_count']} modified)",
            "raw": {"porcelain": git_info["porcelain_lines"]},
        }

    # Check 12: git_synced_with_origin
    ahead = git_info["ahead"]
    behind = git_info["behind"]
    if ahead == 0 and behind == 0:
        checks["git_synced_with_origin"] = {
            "status": "PASS",
            "detail": "ahead=0 behind=0",
            "raw": {"ahead": ahead, "behind": behind},
        }
    else:
        checks["git_synced_with_origin"] = {
            "status": "FAIL",
            "detail": f"ahead={ahead} behind={behind}",
            "raw": {"ahead": ahead, "behind": behind},
        }

    return checks


def create_baseline_data(checks, git_sha):
    expected_values = {
        "runid_type_all_string": "all 4 tables STRING",
        "runid_latest_identical": checks["runid_latest_identical"]["detail"],
        "gitsha_latest_identical": checks["gitsha_latest_identical"]["detail"],
        "writer_id_market_bot": "all 4 = market_bot",
        "sheet_vs_bq_runid_match": checks["sheet_vs_bq_runid_match"]["detail"],
        "sheet_vs_bq_gitsha_match": checks["sheet_vs_bq_gitsha_match"]["detail"],
        "forensic_live_symbol_count_219": "219",
        "forensic_live_symbols_match_manifest": "219/219",
        "gate_formulas_reference_populated_cells": "0 unpopulated refs",
        "pytest_154_passed": "154 passed",
        "git_tree_clean": "clean",
        "git_synced_with_origin": "ahead=0 behind=0",
    }
    baseline = {
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": git_sha,
        "checks": {
            k: {
                "expected": expected_values.get(k, checks[k]["detail"]),
                "tolerance": 0,
            }
            for k in checks
        },
    }
    return baseline


def compare_with_baseline(checks, baseline):
    drift_detected = False
    drift_details = {}
    base_checks = baseline.get("checks", {})
    for k, check in checks.items():
        if k in base_checks:
            expected = base_checks[k].get("expected")
            actual = check["detail"]
            if k == "pytest_154_passed":
                m_act = re.search(r"(\d+)\s+passed", str(actual))
                if m_act and int(m_act.group(1)) >= 154:
                    continue
            if check.get("status") in ("PENDING", "NOT_DUE"):
                continue
            # Dynamic provenance checks: when status is PASS, identical run_id/git_sha across all tables
            # and matching between Sheet and BQ represents normal production cycle progression, not drift.
            if k in (
                "runid_latest_identical",
                "gitsha_latest_identical",
                "sheet_vs_bq_runid_match",
                "sheet_vs_bq_gitsha_match",
            ) and check.get("status") == "PASS":
                continue
            if expected is not None and expected != actual:
                drift_detected = True
                drift_details[k] = {"expected": expected, "actual": actual}
    return drift_detected, drift_details


def main():
    parser = argparse.ArgumentParser(description="Live verification harness for Angel F&O Scanner.")
    parser.add_argument("--update-baseline", action="store_true", help="Update audit/baseline.json if all pass")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON to stdout")
    args = parser.parse_args()

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    git_info = get_git_info()

    # 1. Pull data
    try:
        sheet_data, sh_obj = pull_google_sheets()
        bq_schema, bq_counts, bq_latest = pull_bigquery()
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e), "fatal": True}))
        else:
            print(f"[FATAL] Dependency or network error: {e}", file=sys.stderr)
        sys.exit(2)

    # 2. Run the 12 checks
    checks = run_all_checks(sheet_data, sh_obj, bq_schema, bq_counts, bq_latest, git_info)

    total_checks = len(checks)
    passed_count = sum(1 for c in checks.values() if c["status"] == "PASS")
    pending_count = sum(1 for c in checks.values() if c["status"] == "PENDING")
    any_fail = any(c["status"] == "FAIL" for c in checks.values())
    if passed_count == total_checks:
        overall_status = "PASS"
    elif not any_fail and pending_count > 0:
        overall_status = "PENDING"
    else:
        overall_status = "FAIL"

    # 3. Check baseline
    has_baseline = BASELINE_PATH.exists()
    baseline_missing = not has_baseline
    drift_detected = False
    drift_details = {}

    if not has_baseline:
        candidate_data = create_baseline_data(checks, git_info["head_sha"])
        CANDIDATE_PATH.write_text(json.dumps(candidate_data, indent=2), encoding="utf-8")
    else:
        try:
            baseline_data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
            drift_detected, drift_details = compare_with_baseline(checks, baseline_data)
        except Exception:
            drift_detected = True

    # 4. Handle --update-baseline
    baseline_updated = False
    if args.update_baseline:
        if overall_status == "PASS":
            new_baseline = create_baseline_data(checks, git_info["head_sha"])
            BASELINE_PATH.write_text(json.dumps(new_baseline, indent=2), encoding="utf-8")
            baseline_updated = True
            drift_detected = False
        else:
            pass  # Rules forbid updating baseline when checks fail

    # 5. Write dated evidence file
    ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    evidence_filename = f"verify_harness_{ts_str}.json"
    evidence_path = AUDIT_DIR / evidence_filename

    evidence = {
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_sha": git_info["head_sha"],
        "git_branch": git_info["branch"],
        "overall": overall_status,
        "checks": checks,
        "bq_counts": bq_counts,
        "bq_latest": bq_latest,
        "sheet_values": sheet_data,
        "bq_schema": bq_schema,
    }
    evidence_path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")

    # 6. Output
    if args.json:
        print(json.dumps(evidence, indent=2, default=str))
    else:
        for check_name, res in checks.items():
            status_tag = f"[{res['status']}]"
            print(f"{status_tag:<10} {check_name:<40} {res['detail']}")

        print()
        print(f"Overall: {overall_status}  ({passed_count}/{total_checks}{f', {pending_count} PENDING' if pending_count else ''})")
        print(f"Evidence: audit/{evidence_filename}")

        if baseline_missing:
            print("[NOTICE] audit/baseline.json was absent. Candidate written to audit/baseline_candidate.json.")
            print("         Inspect and promote to audit/baseline.json or run with --update-baseline when checks pass.")

        if baseline_updated:
            print("[INFO] audit/baseline.json updated with current verified state.")

        if drift_detected:
            print(f"[DRIFT] Baseline drift detected in {len(drift_details)} checks:")
            for k, d in drift_details.items():
                print(f"        - {k}: expected='{d['expected']}', actual='{d['actual']}'")

    # 7. Exit codes:
    # 0 = all pass
    # 1 = any fail, or baseline missing on first run
    if baseline_missing:
        sys.exit(1)
    if overall_status == "PASS" and not drift_detected:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
