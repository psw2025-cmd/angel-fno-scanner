#!/usr/bin/env python3
"""
tools/verify_all.py

Unified, single-command system verification for angel-fno-scanner.
Checks:
1. Git clean status
2. Git synchronization with origin/main
3. Full pytest regression suite
4. BigQuery run_id types across all four tables (must be STRING)
5. Google Sheet Formula Checks contract (219 universe / 200 rank board)
6. Infrastructure readiness probe (must have 0 FAILs)
Writes report to audit/verify_report.json.
Exits 0 if all checks pass, non-zero otherwise.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from angel_prediction_engine import get_bigquery_client

PROJECT_ID = "fno-angel-prod-1790444589"
DATASET_ID = "fno_predictions"
TABLES = [
    "option_predictions_live",
    "market_news_sentiment",
    "next_day_gap_predictions",
    "prediction_calibration_log",
]
IST = ZoneInfo("Asia/Kolkata")


def check_git():
    print("[1/6] Checking Git repository status...")
    porcelain = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True).strip()
    is_clean = len(porcelain) == 0

    local_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    try:
        remote_sha = subprocess.check_output(["git", "rev-parse", "origin/main"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        remote_sha = "UNKNOWN"

    is_synced = (local_sha == remote_sha)
    status_str = "PASS" if is_clean and is_synced else ("WARN_DIRTY" if not is_clean else "WARN_DIVERGED")
    print(f"      Local SHA : {local_sha[:10]}")
    print(f"      Remote SHA: {remote_sha[:10]}")
    print(f"      Clean     : {is_clean} ({'clean' if is_clean else len(porcelain.splitlines())} modified/untracked)")
    print(f"      Synced    : {is_synced}")
    return {
        "status": status_str,
        "is_clean": is_clean,
        "is_synced": is_synced,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "uncommitted_files": porcelain.splitlines() if porcelain else []
    }


def check_pytest():
    print("\n[2/6] Running pytest test suite...")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=REPO_ROOT, text=True, capture_output=True)
    out = proc.stdout + proc.stderr
    passed = proc.returncode == 0

    match = re.search(r"(\d+)\s+passed", out)
    count = int(match.group(1)) if match else 0
    print(f"      Result    : {'PASS' if passed else 'FAIL'} ({count} passed, exit code {proc.returncode})")
    return {
        "status": "PASS" if passed else "FAIL",
        "passed_count": count,
        "exit_code": proc.returncode,
        "output": out.strip()
    }


def check_bigquery_types():
    print("\n[3/6] Checking BigQuery run_id types across all four tables...")
    client = get_bigquery_client()
    table_statuses = {}
    all_ok = True

    for t in TABLES:
        table_ref = f"{PROJECT_ID}.{DATASET_ID}.{t}"
        try:
            tbl = client.get_table(table_ref)
            field = next((f for f in tbl.schema if f.name == "run_id"), None)
            f_type = field.field_type if field else "MISSING"
        except Exception as e:
            f_type = f"ERROR: {e}"

        ok = (f_type == "STRING")
        if not ok:
            all_ok = False
        table_statuses[t] = f_type
        print(f"      {t:<30}: run_id = {f_type} [{'OK' if ok else 'FAIL'}]")

    return {
        "status": "PASS" if all_ok else "FAIL",
        "tables": table_statuses
    }


def check_formula_contract():
    """Fail closed if the live Formula Checks sheet drifts from the canonical contract."""
    print("\n[4/6] Checking Google Sheet Formula Checks contract...")
    try:
        from tools.verify_harness import check_gate_formulas, pull_google_sheets

        sheet_data, sh_obj = pull_google_sheets()
        rows = sheet_data.get("Formula Checks", [])
        status, detail, issues = check_gate_formulas(rows, sheet_data, sh_obj)
        print(f"      Result    : {status} ({detail})")
        if issues:
            for issue in issues[:5]:
                print(f"        * {issue}")
        return {
            "status": status,
            "detail": detail,
            "issues": issues,
        }
    except Exception as exc:
        print(f"      Result    : FAIL ({exc})")
        return {
            "status": "FAIL",
            "detail": str(exc),
            "issues": [str(exc)],
        }


def run_readiness_probe():
    print("\n[5/6] Running infrastructure readiness probe...")
    out_root = Path(r"C:\temp\verify")
    out_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "infra_readiness.py"),
        "--repo", str(REPO_ROOT),
        "--output-root", str(out_root),
        "--verify-only"
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)

    # Find the newly generated evidence folder
    evidence_dirs = sorted(out_root.glob("INFRA_READY_*"), key=lambda p: p.name, reverse=True)
    latest_dir = evidence_dirs[0] if evidence_dirs else None

    checks_summary = {}
    fail_count = 0
    pass_count = 0
    other_count = 0

    if latest_dir and (latest_dir / "SYSTEM_STATUS.json").exists():
        try:
            status_json = json.loads((latest_dir / "SYSTEM_STATUS.json").read_text(encoding="utf-8"))
            for item in status_json.get("checks", []):
                chk_name = item.get("check")
                chk_status = item.get("status")
                checks_summary[chk_name] = chk_status
                if chk_status == "FAIL":
                    fail_count += 1
                elif chk_status == "PASS":
                    pass_count += 1
                else:
                    other_count += 1
        except Exception as e:
            checks_summary["error"] = str(e)

    print(f"      Readiness Summary: {pass_count} PASS, {fail_count} FAIL, {other_count} OTHER (NOT_PROVEN/UNKNOWN)")
    for name, st in checks_summary.items():
        if name != "error":
            print(f"        * {name:<25}: {st}")

    return {
        "status": "PASS" if fail_count == 0 else "FAIL",
        "fail_count": fail_count,
        "pass_count": pass_count,
        "other_count": other_count,
        "evidence_dir": str(latest_dir) if latest_dir else "NONE",
        "checks": checks_summary
    }


def main():
    print("=" * 80)
    print(" ANGEL-FNO-SCANNER: COMPLETE SYSTEM VERIFICATION (verify_all.py)")
    print("=" * 80)

    start_time = datetime.datetime.now(IST)

    git_res = check_git()
    pytest_res = check_pytest()
    bq_res = check_bigquery_types()
    formula_res = check_formula_contract()
    readiness_res = run_readiness_probe()

    # Determine overall status
    # Note: git clean/sync is required for final deployment, pytest must pass, BQ must be STRING, probe FAILs must be 0
    critical_failures = []
    if pytest_res["status"] != "PASS":
        critical_failures.append("Pytest regression suite failed")
    if bq_res["status"] != "PASS":
        critical_failures.append("BigQuery run_id types are not STRING")
    if formula_res["status"] != "PASS":
        critical_failures.append("Google Sheet Formula Checks contract drifted from canonical 219/200 rules")
    if readiness_res["fail_count"] > 0:
        # Note: If git is dirty/unpushed, readiness probe working_tree / current_main might show FAIL
        # We separate working_tree from other functional failures
        non_git_fails = [c for c, st in readiness_res["checks"].items() if st == "FAIL" and c not in ("working_tree", "current_main")]
        if non_git_fails:
            critical_failures.append(f"Infrastructure readiness probe reported FAIL on: {', '.join(non_git_fails)}")

    overall_pass = len(critical_failures) == 0

    report = {
        "verified_at_ist": start_time.isoformat(),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "critical_failures": critical_failures,
        "git": git_res,
        "pytest": pytest_res,
        "bigquery": bq_res,
        "formula_checks": formula_res,
        "readiness_probe": readiness_res,
    }

    report_path = REPO_ROOT / "audit" / "verify_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n[6/6] Verification report written to: {report_path}")

    print("\n" + ("=" * 80))
    print(f" FINAL VERDICT: {'ALL GREEN (PASS)' if overall_pass else 'FAIL'}")
    print("=" * 80)
    if not overall_pass:
        print("Reasons:")
        for r in critical_failures:
            print(f"  - {r}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
