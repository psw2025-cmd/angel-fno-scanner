#!/usr/bin/env python3
"""
========================================================================================
   ANGEL F&O - UNIFIED SYSTEM & INFRASTRUCTURE ADMIN TOOLS (admin_tools.py)
========================================================================================
Comprehensive administrative diagnostic and health verification suite covering:
1. Laptop / Host Runtime (OS, Hardware, Memory, Disk, Network, Python Envs, Process PIDs)
2. Safety Constraints (PAPER_MODE=1, LIVE_ORDER_AUTHORITY=0)
3. Indian Market Clock & Calendar Awareness (IST Hours, Holidays, Weekends)
4. Live Broker Connectivity (Angel One SmartAPI, Dhan API)
5. Google Cloud Services (GCP Auth, BigQuery Option Predictions, Sheets SSOT Sync)
6. GitHub Repositories (Branch, Commit Hash, PRs, CI Workflows)

Outputs written directly to:
- C:\\temp\\admin_tools_output.txt
- C:\\temp\\admin_tools_report.json
- C:\\temp\\admin_tools\\admin_tools_<TIMESTAMP>.txt
========================================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent
WORKSTATION_ROOT = Path(r"C:\AngelFNO_Workstation")
TEMP_DIR = Path(r"C:\temp")
TEMP_ADMIN_DIR = TEMP_DIR / "admin_tools"
OUTPUT_TXT = TEMP_DIR / "admin_tools_output.txt"
OUTPUT_JSON = TEMP_DIR / "admin_tools_report.json"

SHEETS_KEY_PATH = Path(r"C:\Users\ADMIN\Downloads\angel_sheets_key.json")
GCP_PROJECT_ID = "fno-angel-prod-1790444589"
SSOT_SHEET_ID = "1xyqUcEtXrh1pdJTO2N-UASZf4fssxbq7bfEjOp4LvOY"

# Add repo to sys.path for market_calendar import
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import market_calendar
except ImportError:
    market_calendar = None


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def run_cmd(cmd: list[str] | str, shell: bool = False, timeout: int = 15) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return -1, "", str(exc)


def probe_http(url: str, timeout: int = 6) -> dict:
    start = time.perf_counter()
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AngelAdminTools/1.0", "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            return {"status": "PASS", "code": resp.status, "latency_ms": elapsed_ms}
    except urllib.error.HTTPError as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        # Any response from server indicates connectivity
        return {"status": "PASS", "code": exc.code, "latency_ms": elapsed_ms}
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        return {"status": "FAIL", "error": str(exc), "latency_ms": elapsed_ms}


# -----------------------------------------------------------------------------
# 1. Host & Laptop Runtime Diagnostics
# -----------------------------------------------------------------------------
def check_host_runtime() -> dict:
    hostname = socket.gethostname()
    os_info = f"{platform.system()} {platform.release()} (Build {platform.version()})"
    arch = platform.machine()
    python_ver = platform.python_version()

    # Disk usage
    disk_c = shutil.disk_usage("C:\\")
    disk_total_gb = round(disk_c.total / (1024**3), 2)
    disk_used_gb = round(disk_c.used / (1024**3), 2)
    disk_free_gb = round(disk_c.free / (1024**3), 2)
    disk_free_pct = round((disk_c.free / disk_c.total) * 100, 1)

    # Memory / CPU via wmic or PowerShell
    mem_total_gb = 0.0
    mem_free_gb = 0.0
    try:
        code, out, _ = run_cmd(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"])
        if code == 0 and out:
            data = json.loads(out)
            mem_total_gb = round(data.get("TotalVisibleMemorySize", 0) / (1024**2), 2)
            mem_free_gb = round(data.get("FreePhysicalMemory", 0) / (1024**2), 2)
    except Exception:
        pass

    # Dedicated processes
    supervisor_pids = []
    scanner_pids = []
    code, out, _ = run_cmd(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*universal_supervisor*' -or $_.CommandLine -like '*scanner.py*' } | Select-Object ProcessId, CommandLine | ConvertTo-Json"])
    if code == 0 and out:
        try:
            procs = json.loads(out)
            if isinstance(procs, dict):
                procs = [procs]
            for p in procs:
                cmdline = p.get("CommandLine", "")
                pid = p.get("ProcessId")
                if "universal_supervisor" in cmdline:
                    supervisor_pids.append(pid)
                elif "scanner.py" in cmdline:
                    scanner_pids.append(pid)
        except Exception:
            pass

    # Task Scheduler status
    code_task, out_task, _ = run_cmd(["schtasks", "/query", "/tn", "AngelSupervisorTask", "/fo", "csv"])
    task_state = "UNKNOWN"
    if code_task == 0:
        lines = [line.strip().strip('"') for line in out_task.splitlines() if line.strip()]
        if len(lines) >= 2:
            parts = [p.strip().strip('"') for p in lines[1].split('","')]
            if len(parts) >= 3:
                task_state = parts[2]

    # SSOT Watchdog task
    code_ssot, out_ssot, _ = run_cmd(["schtasks", "/query", "/tn", "SSOT_MD_Inventory", "/fo", "csv"])
    ssot_state = "UNKNOWN"
    if code_ssot == 0:
        lines = [line.strip().strip('"') for line in out_ssot.splitlines() if line.strip()]
        if len(lines) >= 2:
            parts = [p.strip().strip('"') for p in lines[1].split('","')]
            if len(parts) >= 3:
                ssot_state = parts[2]

    return {
        "hostname": hostname,
        "os": os_info,
        "architecture": arch,
        "python_version": python_ver,
        "disk": {
            "drive": "C:",
            "total_gb": disk_total_gb,
            "used_gb": disk_used_gb,
            "free_gb": disk_free_gb,
            "free_pct": disk_free_pct
        },
        "memory": {
            "total_gb": mem_total_gb,
            "free_gb": mem_free_gb
        },
        "processes": {
            "supervisor_pids": supervisor_pids,
            "scanner_pids": scanner_pids
        },
        "scheduled_tasks": {
            "AngelSupervisorTask": task_state,
            "SSOT_MD_Inventory": ssot_state
        }
    }


# -----------------------------------------------------------------------------
# 2. Safety Settings Verification
# -----------------------------------------------------------------------------
def check_safety() -> dict:
    paper_mode = os.environ.get("PAPER_MODE")
    live_auth = os.environ.get("LIVE_ORDER_AUTHORITY")
    source = "process_env"

    if (paper_mode is None or live_auth is None) and sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                if paper_mode is None:
                    try:
                        val, _ = winreg.QueryValueEx(k, "PAPER_MODE")
                        paper_mode = str(val)
                        source = "registry:HKCU\\Environment"
                    except FileNotFoundError:
                        pass
                if live_auth is None:
                    try:
                        val, _ = winreg.QueryValueEx(k, "LIVE_ORDER_AUTHORITY")
                        live_auth = str(val)
                        source = "registry:HKCU\\Environment"
                    except FileNotFoundError:
                        pass
        except Exception:
            pass

    # Inspect deployed state.json fallback
    if paper_mode is None or live_auth is None:
        for candidate in [
            WORKSTATION_ROOT / "state.json",
            WORKSTATION_ROOT / "angel-agent-supervisor" / "state.json",
            REPO_ROOT / "state.json"
        ]:
            if candidate.exists():
                try:
                    s_data = json.loads(candidate.read_text(encoding="utf-8"))
                    s_safety = s_data.get("safety", {})
                    if paper_mode is None and "PAPER_MODE" in s_safety:
                        paper_mode = str(s_safety["PAPER_MODE"])
                        source = f"deployed_file:{candidate}"
                    if live_auth is None and "LIVE_ORDER_AUTHORITY" in s_safety:
                        live_auth = str(s_safety["LIVE_ORDER_AUTHORITY"])
                        source = f"deployed_file:{candidate}"
                except Exception:
                    pass

    is_safe = (str(paper_mode) == "1" and str(live_auth) == "0")
    return {
        "status": "PASS" if is_safe else "FAIL",
        "PAPER_MODE": paper_mode,
        "LIVE_ORDER_AUTHORITY": live_auth,
        "source": source,
        "safety_guarantee": "Paper trading enforced; live order authority strictly disabled"
    }


# -----------------------------------------------------------------------------
# 3. Market Clock & Holiday Awareness
# -----------------------------------------------------------------------------
def check_market_clock() -> dict:
    now_utc = get_utc_now()
    try:
        from zoneinfo import ZoneInfo
        now_ist_str = now_utc.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        now_ist_str = now_utc.isoformat()

    if market_calendar is not None:
        state = market_calendar.market_session_state(now_utc)
        closure = market_calendar.session_closure(now_utc)
        closure_action = closure.get("action") if isinstance(closure, dict) else "NONE"
        closure_reason = closure.get("reason") if isinstance(closure, dict) else (state.get("summary") or "Market session not currently active")
        is_open = (state.get("status") == "OPEN")
        return {
            "status": state.get("status"),
            "summary": state.get("summary"),
            "date": state.get("date"),
            "now_ist": now_ist_str,
            "is_open": is_open,
            "expect_live_scanner": state.get("expect_live_scanner", False),
            "closure_action": closure_action,
            "closure_reason": closure_reason,
            "expected_scanner_active": is_open
        }
    return {
        "status": "UNKNOWN",
        "summary": "market_calendar module not imported",
        "now_utc": now_utc.isoformat(),
        "now_ist": now_ist_str
    }


# -----------------------------------------------------------------------------
# 4. Broker Connectivity Handshake
# -----------------------------------------------------------------------------
def check_brokers() -> dict:
    angel = probe_http("https://apiconnect.angelone.in")
    dhan = probe_http("https://api.dhan.co")
    overall = (angel.get("status") == "PASS" and dhan.get("status") == "PASS")
    return {
        "status": "PASS" if overall else "FAIL",
        "endpoints": {
            "Angel One SmartAPI": angel,
            "Dhan API": dhan
        }
    }


# -----------------------------------------------------------------------------
# 5. Google Cloud & Google Sheets SSOT
# -----------------------------------------------------------------------------
def check_google_cloud() -> dict:
    results = {
        "project_id": GCP_PROJECT_ID,
        "key_file": {
            "path": str(SHEETS_KEY_PATH),
            "exists": SHEETS_KEY_PATH.exists()
        },
        "bigquery": {
            "status": "UNKNOWN"
        },
        "sheets_ssot": {
            "status": "UNKNOWN"
        }
    }

    # BigQuery probe via Python if packages available
    try:
        import google.auth
        from google.cloud import bigquery
        scopes = ["https://www.googleapis.com/auth/bigquery"]
        creds, _ = google.auth.default(scopes=scopes)
        client = bigquery.Client(project=GCP_PROJECT_ID, credentials=creds)

        query = f"""
        SELECT DATE(snapshot_timestamp) as cycle_date, COUNT(*) as row_count
        FROM `{GCP_PROJECT_ID}.fno_predictions.option_predictions_live`
        GROUP BY cycle_date
        ORDER BY cycle_date DESC
        LIMIT 3
        """
        rows = list(client.query(query).result(timeout=15))
        recent_sessions = [{"date": str(r.cycle_date), "rows": r.row_count} for r in rows]
        results["bigquery"] = {
            "status": "PASS",
            "recent_sessions": recent_sessions,
            "details": f"BigQuery online, successfully read {len(rows)} recent session aggregations"
        }
    except Exception as exc:
        results["bigquery"] = {
            "status": "FAIL",
            "error": str(exc)
        }

    # Google Sheets SSOT Master Inventory check
    try:
        import gspread
        if SHEETS_KEY_PATH.exists():
            gc = gspread.service_account(filename=str(SHEETS_KEY_PATH))
            sh = gc.open_by_key(SSOT_SHEET_ID)
            ws = sh.worksheet("Master_Inventory")
            row_count = ws.row_count
            results["sheets_ssot"] = {
                "status": "PASS",
                "sheet_title": sh.title,
                "worksheet": ws.title,
                "total_rows": row_count,
                "details": f"Connected to SSOT Google Sheet, row count: {row_count}"
            }
        else:
            results["sheets_ssot"] = {
                "status": "FAIL",
                "reason": "Missing service account key file"
            }
    except Exception as exc:
        results["sheets_ssot"] = {
            "status": "FAIL",
            "error": str(exc)
        }

    return results


# -----------------------------------------------------------------------------
# 6. GitHub Repository & Version Control Health
# -----------------------------------------------------------------------------
def check_github_repo() -> dict:
    code_branch, branch_out, _ = run_cmd(["git", "-C", str(REPO_ROOT), "branch", "--show-current"])
    code_sha, sha_out, _ = run_cmd(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"])
    code_status, status_out, _ = run_cmd(["git", "-C", str(REPO_ROOT), "status", "-s"])
    code_gh, gh_out, _ = run_cmd(["gh", "auth", "status"])

    clean = (code_status == 0 and len(status_out.strip()) == 0)
    gh_auth_ok = (code_gh == 0 or "Logged in to github.com" in gh_out)

    # Latest PR info
    code_pr, pr_out, _ = run_cmd(["gh", "pr", "list", "--limit", "1", "--json", "number,title,state,headRefName"])
    latest_pr = {}
    if code_pr == 0 and pr_out:
        try:
            prs = json.loads(pr_out)
            if prs:
                latest_pr = prs[0]
        except Exception:
            pass

    return {
        "repository_path": str(REPO_ROOT),
        "branch": branch_out if code_branch == 0 else "UNKNOWN",
        "latest_commit_sha": sha_out if code_sha == 0 else "UNKNOWN",
        "working_tree_clean": clean,
        "gh_cli_authenticated": gh_auth_ok,
        "latest_pr": latest_pr
    }


# -----------------------------------------------------------------------------
# Main Execution & Output Formatting
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Angel F&O Admin Diagnostics & Health Tools")
    parser.add_argument("--json-only", action="store_true", help="Output only structured JSON to stdout")
    args = parser.parse_args()

    # Ensure C:\temp and C:\temp\admin_tools exist
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_ADMIN_DIR.mkdir(parents=True, exist_ok=True)

    timestamp_utc = get_utc_now().isoformat()
    timestamp_compact = get_utc_now().strftime("%Y%m%dT%H%M%SZ")

    print("[1/6] Auditing Laptop & Host Runtime...")
    host_info = check_host_runtime()

    print("[2/6] Auditing Trading Safety Constraints...")
    safety_info = check_safety()

    print("[3/6] Inspecting Indian Market Clock & Calendar...")
    clock_info = check_market_clock()

    print("[4/6] Pinging Real Live Broker APIs...")
    broker_info = check_brokers()

    print("[5/6] Verifying Google Cloud & Sheets SSOT Services...")
    gcp_info = check_google_cloud()

    print("[6/6] Checking GitHub Repository Status...")
    github_info = check_github_repo()

    # Overall health assessment
    all_pass = (
        safety_info.get("status") == "PASS" and
        broker_info.get("status") == "PASS" and
        gcp_info.get("bigquery", {}).get("status") == "PASS" and
        gcp_info.get("sheets_ssot", {}).get("status") == "PASS"
    )

    report_data = {
        "timestamp_utc": timestamp_utc,
        "overall_status": "PASS" if all_pass else "FAIL",
        "host_runtime": host_info,
        "safety_constraints": safety_info,
        "market_clock": clock_info,
        "brokers": broker_info,
        "google_cloud": gcp_info,
        "github": github_info
    }

    # Format human-readable text
    lines = []
    lines.append("===============================================================================")
    lines.append("        ANGEL F&O - SYSTEM & CLOUD ADMINISTRATION DIAGNOSTICS REPORT           ")
    lines.append("===============================================================================")
    lines.append(f"Timestamp (UTC) : {timestamp_utc}")
    lines.append(f"Overall Status  : {'PASS (ALL SYSTEMS HEALTHY)' if all_pass else 'FAIL / ATTENTION NEEDED'}")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("1. LAPTOP / HOST RUNTIME:")
    lines.append(f"   Hostname      : {host_info['hostname']}")
    lines.append(f"   OS / Platform : {host_info['os']} [{host_info['architecture']}]")
    lines.append(f"   Python        : {host_info['python_version']}")
    lines.append(f"   Disk Space C: : {host_info['disk']['free_gb']} GB Free / {host_info['disk']['total_gb']} GB Total ({host_info['disk']['free_pct']}% available)")
    lines.append(f"   Memory (RAM)  : {host_info['memory']['free_gb']} GB Free / {host_info['memory']['total_gb']} GB Total")
    lines.append(f"   Supervisor PID: {host_info['processes']['supervisor_pids'] or 'None (Allowed when market is closed)'}")
    lines.append(f"   Scanner PID   : {host_info['processes']['scanner_pids'] or 'None (Allowed when market is closed)'}")
    lines.append(f"   AngelSupervisorTask: {host_info['scheduled_tasks']['AngelSupervisorTask']}")
    lines.append(f"   SSOT_MD_Inventory  : {host_info['scheduled_tasks']['SSOT_MD_Inventory']}")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("2. SAFETY & TRIPWIRES:")
    lines.append(f"   Status        : {safety_info['status']}")
    lines.append(f"   PAPER_MODE    : {safety_info['PAPER_MODE']} (Required: 1)")
    lines.append(f"   LIVE_ORDER_AUTH: {safety_info['LIVE_ORDER_AUTHORITY']} (Required: 0)")
    lines.append(f"   Source        : {safety_info['source']}")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("3. INDIAN MARKET CLOCK & CALENDAR:")
    lines.append(f"   Clock State   : {clock_info.get('status')}")
    lines.append(f"   Summary       : {clock_info.get('summary')}")
    lines.append(f"   Current IST   : {clock_info.get('now_ist')}")
    lines.append(f"   Market Open?  : {clock_info.get('is_open')}")
    lines.append(f"   Closure Rule  : {clock_info.get('closure_reason')}")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("4. BROKER CONNECTIVITY (LIVE HTTP HANDSHAKE):")
    for name, ep in broker_info.get("endpoints", {}).items():
        if ep.get("status") == "PASS":
            lines.append(f"   {name:<20}: PASS [HTTP {ep.get('code')}] ({ep.get('latency_ms')} ms)")
        else:
            lines.append(f"   {name:<20}: FAIL [Error: {ep.get('error')}] ({ep.get('latency_ms')} ms)")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("5. GOOGLE CLOUD SERVICES & SHEETS SSOT:")
    lines.append(f"   GCP Project   : {gcp_info['project_id']}")
    lines.append(f"   Key File      : {gcp_info['key_file']['path']} (Exists: {gcp_info['key_file']['exists']})")
    lines.append(f"   BigQuery      : {gcp_info['bigquery'].get('status')} - {gcp_info['bigquery'].get('details', gcp_info['bigquery'].get('error'))}")
    if gcp_info['bigquery'].get("recent_sessions"):
        for sess in gcp_info['bigquery']["recent_sessions"]:
            lines.append(f"      - Session {sess['date']}: {sess['rows']} prediction rows")
    lines.append(f"   Google Sheets : {gcp_info['sheets_ssot'].get('status')} - {gcp_info['sheets_ssot'].get('details', gcp_info['sheets_ssot'].get('error'))}")
    lines.append("-------------------------------------------------------------------------------")
    lines.append("6. GITHUB REPOSITORY & VERSION CONTROL:")
    lines.append(f"   Repo Path     : {github_info['repository_path']}")
    lines.append(f"   Active Branch : {github_info['branch']}")
    lines.append(f"   Latest Commit : {github_info['latest_commit_sha']}")
    lines.append(f"   Working Tree  : {'Clean' if github_info['working_tree_clean'] else 'Modifications present'}")
    lines.append(f"   GitHub CLI    : {'Authenticated' if github_info['gh_cli_authenticated'] else 'Unauthenticated'}")
    if github_info.get("latest_pr"):
        pr = github_info["latest_pr"]
        lines.append(f"   Latest PR     : #{pr.get('number')} '{pr.get('title')}' [{pr.get('state')}]")
    lines.append("===============================================================================")

    full_text = "\n".join(lines)

    # Write outputs
    OUTPUT_TXT.write_text(full_text, encoding="utf-8")
    OUTPUT_JSON.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Timestamped archive copy
    archive_file = TEMP_ADMIN_DIR / f"admin_tools_{timestamp_compact}.txt"
    archive_file.write_text(full_text, encoding="utf-8")

    if args.json_only:
        print(json.dumps(report_data, indent=2))
    else:
        print("\n" + full_text)
        print(f"\n[OK] Results successfully written to:")
        print(f"     1. {OUTPUT_TXT}")
        print(f"     2. {OUTPUT_JSON}")
        print(f"     3. {archive_file}\n")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
