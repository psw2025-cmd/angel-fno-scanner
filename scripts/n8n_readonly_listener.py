#!/usr/bin/env python3
import json
import os
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 5680
SCRIPT = Path("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner/scripts/forward_validation.py")
REPORTS = Path("/mnt/c/AngelFNO_Workstation/reports")
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
            return self._send(200, {"status": "ok", "service": "angel-fno-readonly-listener"})
        if self.path not in COMMANDS:
            return self._send(404, {"status": "error", "message": "unknown endpoint"})
        REPORTS.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc)
        cmd = ["python3", str(SCRIPT), *COMMANDS[self.path]]
        try:
            p = subprocess.run(cmd, cwd=str(SCRIPT.parent.parent), capture_output=True, text=True, timeout=180, check=False)
            evidence = REPORTS / f"n8n_{self.path.strip('/').replace('-', '_')}_{started:%Y%m%d_%H%M%S_%f}.json"
            evidence.write_text(json.dumps({"endpoint": self.path, "started_utc": started.isoformat(), "returncode": p.returncode, "stdout": p.stdout[-12000:], "stderr": p.stderr[-12000:]}, indent=2), encoding="utf-8")
            code = 200 if p.returncode == 0 else 500
            return self._send(code, {"status": "success" if code == 200 else "error", "returncode": p.returncode, "evidence": str(evidence)})
        except Exception as exc:
            return self._send(500, {"status": "error", "message": str(exc)})

    def log_message(self, fmt, *args):
        return

ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
