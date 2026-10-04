"""Fixed-target, read-only host observations; no environment or credentials exported."""
import hashlib
import json
import os
import platform
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

LOCK = threading.Lock()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(target):
    name, url = target
    observed = datetime.now(timezone.utc).isoformat()
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(url, timeout=4) as response:
            status = response.status
            body = json.loads(response.read(4096))
        # Only fixed health payload fields may leave the host.
        safe_body = {"status": body.get("status")} if isinstance(body, dict) else None
        passed = status == 200 and safe_body == {"status": "ok"}
        return name, {"url": url, "observed_at_utc": observed,
                      "http_status": status, "body": safe_body,
                      "verdict": "PASS" if passed else "FAIL"}
    except Exception as exc:
        return name, {"url": url, "observed_at_utc": observed,
                      "verdict": "FAIL", "error_type": type(exc).__name__}


def collect(reports, archive=False):
    with LOCK:
        return _collect(reports, archive)


def _collect(reports, archive):
    now = datetime.now(timezone.utc)
    targets = [("n8n", "http://127.0.0.1:5678/healthz"),
               ("sandbox_api", "http://127.0.0.1:8080/healthz")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        checks = dict(pool.map(probe, targets))
    service = {"verdict": "NOT_VERIFIED"}
    if os.name != "nt":
        try:
            result = subprocess.run(
                ["systemctl", "--user", "show", "n8n.service",
                 "--property=ActiveState,MainPID,ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=4, check=False)
            values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
            pid = int(values.get("MainPID", "0"))
            active = result.returncode == 0 and values.get("ActiveState") == "active" and pid > 0
            service = {"verdict": "PASS" if active else "FAIL", "main_pid": pid,
                       "active_state": values.get("ActiveState"),
                       "started_at": values.get("ActiveEnterTimestamp")}
        except Exception as exc:
            service = {"verdict": "NOT_VERIFIED", "error_type": type(exc).__name__}
    checks["n8n_user_service"] = service
    packet = {
        "schema_version": 1, "evidence_id": str(uuid.uuid4()),
        "observed_at_utc": now.isoformat(),
        "expires_at_utc": (now + timedelta(seconds=90)).isoformat(),
        "runtime": {"host": platform.node(), "collector_os": platform.system(),
                    "collector_context": "host-side readonly listener; not agent workspace",
                    "collector_pid": os.getpid()},
        "checks": checks,
        "status": "VERIFIED_LOCAL" if all(c["verdict"] == "PASS" for c in checks.values()) else "PARTIAL",
        "coordination_bus": "https://github.com/psw2025-cmd/angel-fno-scanner/issues/3",
        "scope": "n8n user-service and two HTTP health endpoints only",
        "not_verified": ["all agent tools", "runner container execution", "market data freshness",
                         "broker orders or authentication", "reboot recovery", "independent peer closure"],
        "interpretation": "Workspace loopback failure is not host failure. Expired or unreachable evidence means NOT_VERIFIED, never PASS.",
        "safety": "read-only collector; grants no production-write or live-order authority",
    }
    encoded = json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()
    packet["payload_sha256"] = hashlib.sha256(encoded).hexdigest()
    # Hash identifies evidence integrity; it is not a digital signature or peer verification.
    directory = Path(reports) / "runtime-evidence"
    directory.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    if archive:
        (directory / (packet["evidence_id"] + ".json")).write_text(raw, encoding="utf-8")
    temp = directory / (packet["evidence_id"] + ".tmp")
    temp.write_text(raw, encoding="utf-8")
    temp.replace(directory / "latest.json")
    return packet
