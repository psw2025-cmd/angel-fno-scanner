#!/usr/bin/env python3
"""Read-only evidence gateway for the Angel F&O n8n control plane."""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, time as dt_time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from n8n_runtime_evidence import collect

HOST = "127.0.0.1"
PORT = 5680

if os.name == "nt":
    REPO_ROOT = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner")
    REPORTS = Path(r"C:\AngelFNO_Workstation\reports")
    PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
else:
    REPO_ROOT = Path("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner")
    REPORTS = Path("/mnt/c/AngelFNO_Workstation/reports")
    PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"

SCRIPT = REPO_ROOT / "scripts" / "forward_validation.py"
POWERBI_INSPECTOR = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/powerbi_inspector.py"
VERIFY_HARNESS = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/verify_harness.py"
COMMANDS = {
    "/pre-market": ["--freeze-target-a", "--snapshot-target-b"],
    "/market": ["--monitor", "market", "--snapshot-target-b"],
    "/post-market": ["--monitor", "postmarket"],
}

sys.path.insert(0, str(REPO_ROOT))
try:
    from market_calendar import IST, is_trading_day
except Exception:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
    def is_trading_day(now):
        return now.astimezone(IST).weekday() < 5


def _run(cmd, timeout=30):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)


def _python_json(code, timeout=30):
    p = _run([str(PYTHON_EXE), "-c", code], timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "child process failed")[-2000:])
    text = p.stdout.strip()
    if not text:
        raise RuntimeError("child process returned no JSON")
    return json.loads(text)


def collect_bigquery():
    code = r"""
import sys, json
from datetime import datetime, timezone
sys.path.insert(0, r'C:\AngelFNO_Workstation\repos\angel-fno-scanner')
from google.cloud import bigquery
import credentials
info = credentials.resolve_service_account_info()
client = bigquery.Client.from_service_account_info(info)
table_id = 'fno-angel-prod-1790444589.fno_predictions.option_predictions_live'
table = client.get_table(table_id)
b = chr(96)
q = f'''SELECT
  COUNT(*) total_rows,
  COUNT(DISTINCT symbol) unique_symbols,
  COUNTIF(run_id IS NOT NULL) with_runid,
  COUNTIF(git_sha IS NOT NULL) with_sha,
  COUNTIF(writer_id IS NOT NULL) with_writer,
  COUNTIF(cycle_id IS NOT NULL) with_cycle,
  COUNTIF(source_timestamp IS NOT NULL) with_source_ts,
  COUNT(DISTINCT run_id) run_ids,
  COUNT(DISTINCT git_sha) git_shas,
  COUNT(DISTINCT writer_id) writer_ids,
  COUNT(DISTINCT cycle_id) cycle_ids,
  MAX(source_timestamp) latest_source,
  MAX(snapshot_timestamp) latest_snapshot
FROM {b}{table_id}{b}'''
r = list(client.query(q).result())[0]
latest = r.latest_source
age = None
if latest is not None:
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age = max(0, (datetime.now(timezone.utc) - latest).total_seconds())
print(json.dumps({
  'status': 'ok',
  'dataset': 'fno_predictions.option_predictions_live',
  'total_rows': r.total_rows,
  'unique_symbols': r.unique_symbols,
  'with_runid': r.with_runid,
  'with_sha': r.with_sha,
  'with_writer': r.with_writer,
  'with_cycle': r.with_cycle,
  'with_source_ts': r.with_source_ts,
  'run_ids': r.run_ids,
  'git_shas': r.git_shas,
  'writer_ids': r.writer_ids,
  'cycle_ids': r.cycle_ids,
  'latest_source_utc': str(r.latest_source),
  'latest_snapshot_utc': str(r.latest_snapshot),
  'source_age_seconds': age,
  'schema_field_count': len(table.schema),
}, default=str))
"""
    return _python_json(code, timeout=35)


def collect_sheets():
    code = r"""
import sys, json
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0, r'C:\AngelFNO_Workstation\repos\angel-fno-scanner')
import gspread, credentials
IST = ZoneInfo('Asia/Kolkata')
info = credentials.resolve_service_account_info()
gc = gspread.service_account_from_dict(info)
sh = gc.open_by_key('1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs')
tabs = [w.title for w in sh.worksheets()]
fl = sh.worksheet('FORENSIC_LIVE').get_all_values()
symbols = [str(r[1]).strip().upper() for r in fl[1:] if len(r) > 1 and str(r[1]).strip()]
hb = sh.worksheet('HEARTBEAT').get_all_values()
last_fetch = hb[1][0].strip() if len(hb) > 1 and hb[1] else ''
age = None
if last_fetch:
    try:
        stamp = datetime.strptime(last_fetch[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=IST)
        age = max(0, (datetime.now(IST) - stamp).total_seconds())
    except Exception:
        pass
pub = sh.worksheet('PUBLICATION_STATUS').get_all_values()
publication_state = pub[1][0].strip() if len(pub) > 1 and pub[1] else 'MISSING'
publication_cycle = pub[1][1].strip() if len(pub) > 1 and len(pub[1]) > 1 else ''
formula = sh.worksheet('Formula Checks').get_all_values(value_render_option='FORMATTED_VALUE')
error_tokens = {'#REF!', '#VALUE!', '#N/A', '#DIV/0!', '#NAME?', '#NUM!'}
formula_error_count = 0
failed_gate_count = 0
for row in formula:
    for cell in row:
        v = str(cell).strip().upper()
        if v in error_tokens:
            formula_error_count += 1
        if v == 'FAIL' or v == 'BLOCKED' or v.startswith('BLOCKED '):
            failed_gate_count += 1
print(json.dumps({
  'status': 'ok',
  'spreadsheet_id': sh.id,
  'total_tabs': len(tabs),
  'tabs': tabs,
  'forensic_live_rows': max(0, len(fl)-1),
  'forensic_live_symbols': len(symbols),
  'forensic_live_unique_symbols': len(set(symbols)),
  'heartbeat_last_fetch_ist': last_fetch,
  'heartbeat_age_seconds': age,
  'publication_state': publication_state,
  'publication_cycle_id': publication_cycle,
  'formula_error_count': formula_error_count,
  'failed_gate_count': failed_gate_count,
}, default=str))
"""
    return _python_json(code, timeout=35)


def collect_powerbi():
    p = _run([str(PYTHON_EXE), POWERBI_INSPECTOR], timeout=20)
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError((p.stderr or "Power BI inspector failed")[-1000:])
    return json.loads(p.stdout.strip())


def collect_github():
    url = "https://api.github.com/repos/psw2025-cmd/angel-fno-scanner/actions/workflows/market_bot.yml/runs?per_page=20"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "angel-fno-readonly-listener",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    runs = payload.get("workflow_runs", [])
    now_ist = datetime.now(IST)
    today = now_ist.date()
    slim = []
    for run in runs:
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        created_ist = created.astimezone(IST)
        slim.append({
            "id": run.get("id"),
            "event": run.get("event"),
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"),
            "created_at_ist": created_ist.isoformat(),
            "head_sha": run.get("head_sha"),
            "html_url": run.get("html_url"),
            "is_today_ist": created_ist.date() == today,
            "age_seconds": max(0, (now_ist - created_ist).total_seconds()),
        })
    today_runs = [r for r in slim if r["is_today_ist"]]
    active = [r for r in slim if r["status"] in ("queued", "in_progress", "waiting", "pending")]
    recent = [r for r in today_runs if r["age_seconds"] <= 1800]
    return {
        "status": "ok",
        "latest": slim[0] if slim else None,
        "today_run_count": len(today_runs),
        "active_run_count": len(active),
        "recent_or_active": bool(active or recent),
        "runs": slim[:8],
    }


def market_is_open_now():
    now = datetime.now(IST)
    try:
        trading_day = is_trading_day(now)
    except Exception:
        trading_day = now.weekday() < 5
    local_time = now.time().replace(tzinfo=None)
    return bool(trading_day and dt_time(9, 15) <= local_time <= dt_time(15, 30))


def build_orchestrator_status():
    now = datetime.now(IST)
    market_open = market_is_open_now()
    errors = {}
    components = {}

    for name, fn in (
        ("runtime", lambda: collect(REPORTS)),
        ("bigquery", collect_bigquery),
        ("sheets", collect_sheets),
        ("github", collect_github),
        ("powerbi", collect_powerbi),
    ):
        try:
            components[name] = fn()
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
            components[name] = {"status": "error"}

    bq = components["bigquery"]
    sh = components["sheets"]
    gh = components["github"]
    rt = components["runtime"]

    checks = {
        "runtime_local": rt.get("status") == "VERIFIED_LOCAL",
        "bq_universe_219": bq.get("total_rows") == 219 and bq.get("unique_symbols") == 219,
        "bq_lineage_complete": all(bq.get(k) == 219 for k in ("with_runid", "with_sha", "with_writer", "with_cycle", "with_source_ts"))
            and all(bq.get(k) == 1 for k in ("run_ids", "git_shas", "writer_ids", "cycle_ids")),
        "sheets_universe_219": sh.get("forensic_live_rows") == 219 and sh.get("forensic_live_unique_symbols") == 219,
        "sheets_publication_verified": sh.get("publication_state") == "VERIFIED",
        "sheets_formula_integrity": sh.get("formula_error_count") == 0 and sh.get("failed_gate_count") == 0,
    }
    if market_open:
        checks["bq_fresh_during_market"] = isinstance(bq.get("source_age_seconds"), (int, float)) and bq["source_age_seconds"] <= 1200
        checks["sheets_fresh_during_market"] = isinstance(sh.get("heartbeat_age_seconds"), (int, float)) and sh["heartbeat_age_seconds"] <= 1200
        checks["github_market_cycle_recent_or_active"] = gh.get("recent_or_active") is True
    else:
        checks["bq_fresh_during_market"] = True
        checks["sheets_fresh_during_market"] = True
        checks["github_market_cycle_recent_or_active"] = True

    verdict = "HEALTHY" if not errors and all(checks.values()) else "ATTENTION_REQUIRED"
    return {
        "timestamp_ist": now.isoformat(),
        "market_open": market_open,
        "orchestrator_verdict": verdict,
        "checks": checks,
        "errors": errors,
        "components": components,
        "read_only": True,
    }


def build_diagnosis():
    status = build_orchestrator_status()
    failed = [name for name, ok in status["checks"].items() if not ok]
    return {
        "status": "PASS" if not failed and not status["errors"] else "FAIL_CLOSED",
        "timestamp_ist": status["timestamp_ist"],
        "failed_checks": failed,
        "errors": status["errors"],
        "recommended_action": "Repair only the failed component, then re-run verification. No automatic data mutation was performed.",
        "orchestrator_verdict": status["orchestrator_verdict"],
        "read_only": True,
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        try:
            if self.path == "/health":
                return self._send(200, {"status": "ok", "service": "angel-fno-readonly-listener", "port": PORT, "read_only": True})
            if self.path == "/runtime-evidence":
                return self._send(200, collect(REPORTS, archive=True))
            if self.path == "/bigquery":
                return self._send(200, collect_bigquery())
            if self.path == "/sheets":
                return self._send(200, collect_sheets())
            if self.path == "/github":
                return self._send(200, collect_github())
            if self.path == "/powerbi":
                return self._send(200, collect_powerbi())
            if self.path == "/orchestrator-status":
                return self._send(200, build_orchestrator_status())
            if self.path == "/diagnose":
                return self._send(200, build_diagnosis())
            if self.path == "/auto-remediate":
                return self._send(410, {
                    "status": "DISABLED",
                    "reason": "Unsafe automatic data mutation has been removed. Use /diagnose and a controlled repair branch.",
                    "read_only": True,
                })
            if self.path == "/verification-harness":
                p = _run([str(PYTHON_EXE), VERIFY_HARNESS, "--json"], timeout=150)
                if p.stdout.strip():
                    try:
                        return self._send(200 if p.returncode == 0 else 500, json.loads(p.stdout.strip()))
                    except Exception:
                        pass
                return self._send(200 if p.returncode == 0 else 500, {
                    "status": "PASS" if p.returncode == 0 else "FAIL",
                    "stdout": p.stdout.strip()[-4000:],
                    "stderr": p.stderr.strip()[-2000:],
                })
            if self.path not in COMMANDS:
                return self._send(404, {"status": "error", "message": "unknown endpoint"})

            REPORTS.mkdir(parents=True, exist_ok=True)
            started = datetime.now(timezone.utc)
            cmd = ["python3", str(SCRIPT), *COMMANDS[self.path]]
            env = {**os.environ, "ANGEL_REPORTS_DIR": str(REPORTS)}
            p = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=180, check=False)
            evidence = REPORTS / f"n8n_{self.path.strip('/').replace('-', '_')}_{started:%Y%m%d_%H%M%S_%f}.json"
            evidence.write_text(json.dumps({
                "endpoint": self.path,
                "started_utc": started.isoformat(),
                "returncode": p.returncode,
                "stdout": p.stdout[-12000:],
                "stderr": p.stderr[-12000:],
            }, indent=2), encoding="utf-8")
            return self._send(200 if p.returncode == 0 else 500, {
                "status": "success" if p.returncode == 0 else "error",
                "returncode": p.returncode,
                "evidence": str(evidence),
            })
        except Exception as exc:
            return self._send(503, {
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc)[:1500],
                "read_only": True,
            })

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
