#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from n8n_runtime_evidence import collect

HOST = "127.0.0.1"
PORT = 5680
if os.name == "nt":
    SCRIPT = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner\scripts\forward_validation.py")
    REPORTS = Path(r"C:\AngelFNO_Workstation\reports")
    PYTHON_EXE = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe")
else:
    SCRIPT = Path("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner/scripts/forward_validation.py")
    REPORTS = Path("/mnt/c/AngelFNO_Workstation/reports")
    PYTHON_EXE = Path("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner/.venv/Scripts/python.exe")
COMMANDS = {
    "/pre-market": ["--freeze-target-a", "--snapshot-target-b"],
    "/market": ["--monitor", "market", "--snapshot-target-b"],
    "/post-market": ["--monitor", "postmarket"],
}

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload):
        raw = json.dumps(payload, sort_keys=True).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == "/health":
            try:
                evidence = collect(REPORTS)
            except Exception as exc:
                evidence = {"status": "NOT_VERIFIED", "error_type": type(exc).__name__}
            return self._send(200, {"status": "ok", "service": "angel-fno-readonly-listener", "port": PORT,
                                    "runtime_evidence": evidence})

        if self.path == "/runtime-evidence":
            try:
                return self._send(200, collect(REPORTS, archive=True))
            except Exception as exc:
                return self._send(503, {"status": "NOT_VERIFIED", "error_type": type(exc).__name__})

        if self.path == "/bigquery":
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
                p = subprocess.run([str(PYTHON_EXE), "-c", code_snippet], capture_output=True, text=True, timeout=20, check=False)
                if p.returncode == 0:
                    return self._send(200, json.loads(p.stdout.strip()))
                else:
                    return self._send(500, {"status": "error", "error": p.stderr.strip()[:500]})
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})

        if self.path == "/sheets":
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
                p = subprocess.run([str(PYTHON_EXE), "-c", code_snippet], capture_output=True, text=True, timeout=20, check=False)
                if p.returncode == 0:
                    return self._send(200, json.loads(p.stdout.strip()))
                else:
                    return self._send(500, {"status": "error", "error": p.stderr.strip()[:500]})
            except Exception as e:
                return self._send(500, {"status": "error", "message": str(e)})
        if self.path not in COMMANDS:
            return self._send(404, {"status": "error", "message": "unknown endpoint"})
        REPORTS.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc)
        cmd = ["python3", str(SCRIPT), *COMMANDS[self.path]]
        try:
            env = {**os.environ, "ANGEL_REPORTS_DIR": str(REPORTS)}
            p = subprocess.run(cmd, cwd=str(SCRIPT.parent.parent), env=env, capture_output=True, text=True, timeout=180, check=False)
            evidence = REPORTS / f"n8n_{self.path.strip('/').replace('-', '_')}_{started:%Y%m%d_%H%M%S_%f}.json"
            evidence.write_text(json.dumps({"endpoint": self.path, "started_utc": started.isoformat(), "returncode": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}, indent=2), encoding="utf-8")
            code = 200 if p.returncode == 0 else 500
            return self._send(code, {"status": "success" if code == 200 else "error", "returncode": p.returncode, "evidence": str(evidence)})
        except Exception as exc:
            return self._send(500, {"status": "error", "message": str(exc)})

    def log_message(self, fmt, *args):
        return

ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
