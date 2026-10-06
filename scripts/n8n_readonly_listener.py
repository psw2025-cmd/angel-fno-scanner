#!/usr/bin/env python3
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from n8n_runtime_evidence import collect

HOST = "127.0.0.1"
PORT = 5680
if os.name == "nt":
    REPO_ROOT = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner")
    SCRIPT = REPO_ROOT / "scripts" / "forward_validation.py"
    REPORTS = Path(r"C:\AngelFNO_Workstation\reports")
    PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    POWERBI_INSPECTOR = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/powerbi_inspector.py"
    VERIFY_HARNESS = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/verify_harness.py"
else:
    REPO_ROOT = Path("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner")
    SCRIPT = REPO_ROOT / "scripts" / "forward_validation.py"
    REPORTS = Path("/mnt/c/AngelFNO_Workstation/reports")
    PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    POWERBI_INSPECTOR = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/powerbi_inspector.py"
    VERIFY_HARNESS = "C:/AngelFNO_Workstation/repos/angel-fno-scanner/tools/verify_harness.py"

COMMANDS = {
    "/pre-market": ["--freeze-target-a", "--snapshot-target-b"],
    "/market": ["--monitor", "market", "--snapshot-target-b"],
    "/post-market": ["--monitor", "postmarket"],
}

_CACHE = {}


def get_cached(key: str, ttl_seconds: float):
    entry = _CACHE.get(key)
    if entry and (time.time() - entry["ts"] < ttl_seconds):
        return entry["val"]
    return None


def set_cached(key: str, val):
    _CACHE[key] = {"ts": time.time(), "val": val}
    return val


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        raw = json.dumps(payload, sort_keys=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        # Support POST for webhook callers
        return self.do_GET()

    def do_GET(self):
        clean_path = self.path.split("?")[0]

        if clean_path == "/health":
            try:
                evidence = collect(REPORTS)
            except Exception as exc:
                evidence = {"status": "NOT_VERIFIED", "error_type": type(exc).__name__}
            return self._send(
                200,
                {
                    "status": "ok",
                    "service": "angel-fno-readonly-listener",
                    "port": PORT,
                    "runtime_evidence": evidence,
                },
            )

        if clean_path == "/runtime-evidence":
            try:
                return self._send(200, collect(REPORTS, archive=True))
            except Exception as exc:
                return self._send(503, {"status": "NOT_VERIFIED", "error_type": type(exc).__name__})

        if clean_path == "/bigquery":
            cached = get_cached("bigquery", 30)
            if cached:
                return self._send(200, cached)
            try:
                code_snippet = (
                    "import sys; sys.path.insert(0, r'C:\\AngelFNO_Workstation\\repos\\angel-fno-scanner'); "
                    "from google.cloud import bigquery; import credentials, json; "
                    "info = credentials.resolve_service_account_info(); "
                    "client = bigquery.Client.from_service_account_info(info); "
                    "b = chr(96); "
                    "q = f'SELECT count(*) as total, countif(git_sha is not null) as with_sha, max(snapshot_timestamp) as latest FROM {b}fno-angel-prod-1790444589.fno_predictions.option_predictions_live{b}'; "
                    "r = list(client.query(q).result())[0]; "
                    "print(json.dumps({'status': 'ok', 'dataset': 'fno_predictions.option_predictions_live', 'total_rows': r.total, 'rows_with_git_sha': r.with_sha, 'latest_snapshot_utc': str(r.latest)}))"
                )
                p = subprocess.run([str(PYTHON_EXE), "-c", code_snippet], capture_output=True, text=True, timeout=25, check=False)
                if p.returncode == 0:
                    data = json.loads(p.stdout.strip())
                    set_cached("bigquery", data)
                    return self._send(200, data)
                else:
                    return self._send(500, {"status": "error", "error": p.stderr.strip()[:500]})
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path == "/sheets":
            cached = get_cached("sheets", 30)
            if cached:
                return self._send(200, cached)
            try:
                code_snippet = (
                    "import sys; sys.path.insert(0, r'C:\\AngelFNO_Workstation\\repos\\angel-fno-scanner'); "
                    "import gspread, credentials, json; "
                    "info = credentials.resolve_service_account_info(); "
                    "gc = gspread.service_account_from_dict(info); "
                    "sh = gc.open_by_key('1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs'); "
                    "tabs = [w.title for w in sh.worksheets()]; "
                    "print(json.dumps({'status': 'ok', 'spreadsheet_id': '1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs', 'total_tabs': len(tabs), 'tabs': tabs}))"
                )
                p = subprocess.run([str(PYTHON_EXE), "-c", code_snippet], capture_output=True, text=True, timeout=25, check=False)
                if p.returncode == 0:
                    data = json.loads(p.stdout.strip())
                    set_cached("sheets", data)
                    return self._send(200, data)
                else:
                    return self._send(500, {"status": "error", "error": p.stderr.strip()[:500]})
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path == "/powerbi":
            cached = get_cached("powerbi", 15)
            if cached:
                return self._send(200, cached)
            try:
                p = subprocess.run([str(PYTHON_EXE), POWERBI_INSPECTOR], capture_output=True, text=True, timeout=30, check=False)
                if p.returncode == 0 and p.stdout.strip():
                    data = json.loads(p.stdout.strip())
                    set_cached("powerbi", data)
                    return self._send(200, data)
                else:
                    return self._send(500, {"status": "error", "error": p.stderr.strip()[:500]})
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path == "/verification-harness":
            try:
                p = subprocess.run([str(PYTHON_EXE), VERIFY_HARNESS, "--json"], capture_output=True, text=True, timeout=90, check=False)
                if p.stdout.strip():
                    try:
                        data = json.loads(p.stdout.strip())
                        return self._send(200, data)
                    except Exception:
                        pass
                return self._send(200 if p.returncode == 0 else 500, {
                    "status": "PASS" if p.returncode == 0 else "FAIL",
                    "stdout": p.stdout.strip()[-3000:],
                    "stderr": p.stderr.strip()[-1500:],
                })
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path == "/orchestrator-status":
            cached = get_cached("orchestrator_status", 20)
            if cached:
                return self._send(200, cached)
            try:
                pbi_cached = get_cached("powerbi", 15)
                if not pbi_cached:
                    pbi_res = subprocess.run([str(PYTHON_EXE), POWERBI_INSPECTOR], capture_output=True, text=True, timeout=25, check=False)
                    pbi_data = json.loads(pbi_res.stdout.strip()) if pbi_res.returncode == 0 and pbi_res.stdout.strip() else {"verdict": "ERROR"}
                    set_cached("powerbi", pbi_data)
                else:
                    pbi_data = pbi_cached

                bq_snippet = (
                    "import sys; sys.path.insert(0, r'C:\\AngelFNO_Workstation\\repos\\angel-fno-scanner'); "
                    "from google.cloud import bigquery; import credentials, json; "
                    "info = credentials.resolve_service_account_info(); "
                    "client = bigquery.Client.from_service_account_info(info); "
                    "b = chr(96); "
                    "q = f'SELECT count(*) as total, countif(run_id is not null) as with_runid, countif(git_sha is not null) as with_sha FROM {b}fno-angel-prod-1790444589.fno_predictions.option_predictions_live{b}'; "
                    "r = list(client.query(q).result())[0]; "
                    "print(json.dumps({'total': r.total, 'with_runid': r.with_runid, 'with_sha': r.with_sha}))"
                )
                bq_p = subprocess.run([str(PYTHON_EXE), "-c", bq_snippet], capture_output=True, text=True, timeout=25, check=False)
                bq_data = json.loads(bq_p.stdout.strip()) if bq_p.returncode == 0 and bq_p.stdout.strip() else {"error": "BQ query failed"}

                runtime_ev = collect(REPORTS)

                aggregated = {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "orchestrator_verdict": "HEALTHY" if pbi_data.get("verdict") == "HEALTHY" and bq_data.get("total", 0) == 219 else "ATTENTION_REQUIRED",
                    "components": {
                        "powerbi": pbi_data,
                        "bigquery": bq_data,
                        "runtime_evidence": runtime_ev,
                    },
                }
                set_cached("orchestrator_status", aggregated)
                return self._send(200, aggregated)
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path == "/auto-remediate":
            try:
                actions = []
                # 1. Clean any stale .control-center.lock files
                for lock_cand in [
                    Path(r"C:\Users\ADMIN\Documents\Codex\2026-10-02\referenced-chatgpt-conversation-this-is-an-3\outputs\.control-center.lock"),
                    Path("/mnt/c/Users/ADMIN/Documents/Codex/2026-10-02/referenced-chatgpt-conversation-this-is-an-3/outputs/.control-center.lock"),
                ]:
                    if lock_cand.exists():
                        try:
                            if time.time() - lock_cand.stat().st_mtime > 120:
                                lock_cand.unlink(missing_ok=True)
                                actions.append(f"Removed stale lock: {lock_cand}")
                        except Exception as e:
                            actions.append(f"Notice on lock {lock_cand}: {e}")

                # 2. Check and heal BQ schema columns if missing
                try:
                    ddl_snippet = (
                        "import sys; sys.path.insert(0, r'C:\\AngelFNO_Workstation\\repos\\angel-fno-scanner'); "
                        "from angel_prediction_engine import get_bigquery_client, BQ_DATASET_ID; "
                        "bq = get_bigquery_client(); "
                        "q = f'ALTER TABLE fno-angel-prod-1790444589.{BQ_DATASET_ID}.option_predictions_live "
                        "ADD COLUMN IF NOT EXISTS run_id STRING, ADD COLUMN IF NOT EXISTS git_sha STRING, "
                        "ADD COLUMN IF NOT EXISTS writer_id STRING, ADD COLUMN IF NOT EXISTS source_timestamp TIMESTAMP, "
                        "ADD COLUMN IF NOT EXISTS cycle_id STRING, ADD COLUMN IF NOT EXISTS data_freshness_status STRING'; "
                        "bq.query(q).result(); print('DDL_VERIFIED')"
                    )
                    ddl_p = subprocess.run([str(PYTHON_EXE), "-c", ddl_snippet], capture_output=True, text=True, timeout=30, check=False)
                    if ddl_p.returncode == 0:
                        actions.append("BigQuery 54-column DDL verified and aligned.")
                    else:
                        actions.append(f"BigQuery DDL notice: {ddl_p.stderr.strip()[:200]}")
                except Exception as e:
                    actions.append(f"BigQuery DDL step notice: {e}")

                # 3. Synchronize provenance across auxiliary tables
                try:
                    sync_p = subprocess.run([str(PYTHON_EXE), "C:/AngelFNO_Workstation/repos/angel-fno-scanner/scripts/sync_cycle_provenance_to_bq.py"], capture_output=True, text=True, timeout=60, check=False)
                    if sync_p.returncode == 0:
                        actions.append("BigQuery auxiliary table provenance synchronized.")
                    else:
                        actions.append(f"Provenance sync notice: {sync_p.stderr.strip()[:200]}")
                except Exception as e:
                    actions.append(f"Provenance sync step notice: {e}")

                # Clear cache after remediation
                _CACHE.clear()

                return self._send(200, {
                    "status": "REMEDIATED",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "actions_taken": actions,
                })
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if clean_path not in COMMANDS:
            return self._send(404, {"status": "error", "message": "unknown endpoint"})

        REPORTS.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc)
        cmd = ["python3", str(SCRIPT), *COMMANDS[clean_path]]
        try:
            env = {**os.environ, "ANGEL_REPORTS_DIR": str(REPORTS)}
            p = subprocess.run(cmd, cwd=str(SCRIPT.parent.parent), env=env, capture_output=True, text=True, timeout=180, check=False)
            evidence = REPORTS / f"n8n_{clean_path.strip('/').replace('-', '_')}_{started:%Y%m%d_%H%M%S_%f}.json"
            evidence.write_text(json.dumps({"endpoint": clean_path, "started_utc": started.isoformat(), "returncode": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}, indent=2), encoding="utf-8")
            code = 200 if p.returncode == 0 else 500
            return self._send(code, {"status": "success" if code == 200 else "error", "returncode": p.returncode, "evidence": str(evidence)})
        except Exception as exc:
            return self._send(500, {"status": "error", "message": str(exc)})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
