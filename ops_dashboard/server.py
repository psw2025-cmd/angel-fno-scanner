"""Authenticated, loopback-only evidence API for the operations dashboard."""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from ops_dashboard.evidence import APP_ROOT, MAX_TREE_ITEMS, ROOT, SENSITIVE_PATH_RE, EvidenceCollector, redact_text, export_issue_package

HOST = "127.0.0.1"
PORT = int(os.environ.get("ANGEL_DASHBOARD_PORT", "8765"))
INDEX = Path(__file__).with_name("index.html")
OWNER_CHECK = Path(__file__).with_name("verify_loopback_owner.ps1")
SESSION_NAME = "angel_dashboard_session"
SESSION_SECONDS = 12 * 60 * 60
MAX_BODY = 32_000
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class AuthStore:
    """Short-lived cookie signer; identity is established from the local OS process."""
    def __init__(self):
        self._signing_key = secrets.token_bytes(32)

    def session_cookie(self, now: int | None = None) -> str:
        issued = int(time.time() if now is None else now)
        payload = json.dumps({"exp": issued + SESSION_SECONDS, "nonce": secrets.token_urlsafe(12)}, separators=(",", ":")).encode("utf-8")
        body = _b64(payload)
        signature = hmac.new(self._signing_key, body.encode("ascii"), hashlib.sha256).digest()
        return body + "." + _b64(signature)

    def valid_cookie(self, cookie_value: str | None, now: int | None = None) -> bool:
        if not cookie_value or "." not in cookie_value:
            return False
        try:
            body, sig = cookie_value.split(".", 1)
            expected = hmac.new(self._signing_key, body.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(sig)):
                return False
            payload = json.loads(_unb64(body))
            return isinstance(payload.get("exp"), int) and payload["exp"] > int(time.time() if now is None else now)
        except (ValueError, TypeError, json.JSONDecodeError):
            return False


def same_windows_user_process(client_port: int, server_port: int = PORT) -> bool:
    """Authenticate a loopback peer by its owning process' Windows SID."""
    if os.name != "nt" or not (1 <= int(client_port) <= 65535):
        return False
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(OWNER_CHECK), "-ClientPort", str(client_port), "-ServerPort", str(server_port)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=4, shell=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "MATCH"
    except (OSError, subprocess.TimeoutExpired):
        return False


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler):
        super().__init__(address, handler)
        self.auth_store = AuthStore()
        self.collector = EvidenceCollector()
        self._snapshot_lock = threading.Lock()
        self._latest_snapshot = None
        self._last_snapshot_at = 0.0

    def latest_snapshot(self, refresh: bool = False):
        with self._snapshot_lock:
            if self._latest_snapshot is None or refresh or time.monotonic() - self._last_snapshot_at > 25:
                self._latest_snapshot = self.collector.collect(persist=True, force_remote=refresh)
                self._last_snapshot_at = time.monotonic()
            return self._latest_snapshot


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server: DashboardServer
    protocol_version = "HTTP/1.1"
    sys_version = "AngelOps"
    server_version = "AngelOps/1.0"

    def log_message(self, fmt, *args):
        # Request paths and query text may contain user-provided data; log route only.
        route = urlparse(self.path).path[:160]
        print(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {self.client_address[0]} {self.command} {route}")

    def _host_valid(self) -> bool:
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        return (self.headers.get("Host", "").lower() in allowed and self.client_address[0] in {"127.0.0.1", "::1"})

    def _origin_valid(self) -> bool:
        origin = self.headers.get("Origin")
        port = self.server.server_address[1]
        return origin is None or origin.lower() in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def _send(self, status: int, payload: bytes, content_type: str, headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Frame-Options", "DENY")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def _json(self, status: int, payload: dict, headers: dict[str, str] | None = None):
        self._send(status, _json_bytes(payload), "application/json; charset=utf-8", headers)

    def _cookie_value(self) -> str | None:
        raw = self.headers.get("Cookie", "")
        try:
            cookies = SimpleCookie()
            cookies.load(raw)
            return cookies[SESSION_NAME].value if SESSION_NAME in cookies else None
        except Exception:
            return None

    def _authenticated(self) -> bool:
        if self.server.auth_store.valid_cookie(self._cookie_value()):
            return True
        return self.client_address[0] in {"127.0.0.1", "::1"} and same_windows_user_process(self.client_address[1], self.server.server_address[1])

    def _require_auth(self) -> bool:
        if self._authenticated():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "AUTH_REQUIRED"})
        return False

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid content length")
        if length < 0 or length > MAX_BODY:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8")) if raw else {}
        if not isinstance(value, dict):
            raise ValueError("JSON object required")
        return value

    def do_GET(self):
        if not self._host_valid():
            self._json(HTTPStatus.BAD_REQUEST, {"error": "LOCALHOST_ONLY"})
            return
        route = urlparse(self.path)
        if route.path == "/" or route.path == "/index.html":
            try:
                body = INDEX.read_bytes()
            except OSError:
                self._send(HTTPStatus.NOT_FOUND, b"Dashboard asset missing", "text/plain; charset=utf-8")
                return
            self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
            return
        if route.path == "/api/v1/auth/status":
            authenticated = self._authenticated()
            headers = {"Set-Cookie": f"{SESSION_NAME}={self.server.auth_store.session_cookie()}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}"} if authenticated and not self.server.auth_store.valid_cookie(self._cookie_value()) else None
            self._json(HTTPStatus.OK, {"authenticated": authenticated, "configured": os.name == "nt", "auth_method": "WINDOWS_LOCAL_PROCESS_SID", "loopback_only": True}, headers)
            return
        if not route.path.startswith("/api/v1/"):
            self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
            return
        if not self._require_auth():
            return
        query = parse_qs(route.query, keep_blank_values=False)
        if route.path == "/api/v1/overview":
            self._json(HTTPStatus.OK, self.server.latest_snapshot(refresh=query.get("refresh", [""])[0] == "1"))
        elif route.path == "/api/v1/history":
            self._json(HTTPStatus.OK, self.server.collector.history(int(query.get("limit", ["250"])[0])))
        elif route.path == "/api/v1/exports":
            path = self.server.collector.store.root.parent / "exports" / "export-history.jsonl"
            rows = []
            try:
                with path.open("r", encoding="utf-8") as stream:
                    for line in stream:
                        if line.strip():
                            rows.append(json.loads(line))
            except (OSError, ValueError):
                pass
            safe_rows = [{"issue_id": redact_text(row.get("issue_id", ""), 100), "created_at": redact_text(row.get("created_at", ""), 80), "package": redact_text(row.get("package", ""), 140), "download_url": f"/api/v1/exports/{row.get('package', '')}.zip"} for row in rows[-100:] if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}-\d{8}T\d{6}Z", str(row.get("package", "")))]
            self._json(HTTPStatus.OK, {"exports": safe_rows})
        elif route.path.startswith("/api/v1/exports/"):
            package_file = route.path.removeprefix("/api/v1/exports/")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}-\d{8}T\d{6}Z\.zip", package_file):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_EXPORT_NAME"})
                return
            exports_root = self.server.collector.store.root.parent / "exports"
            target = (exports_root / package_file).resolve()
            if not target.is_relative_to(exports_root.resolve()) or not target.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"error": "EXPORT_NOT_FOUND"})
                return
            content = target.read_bytes()
            self._send(HTTPStatus.OK, content, "application/zip", {"Content-Disposition": f'attachment; filename="{package_file}"'})
        elif route.path == "/api/v1/repository/tree":
            self.server.latest_snapshot()
            self._json(HTTPStatus.OK, self.server.collector.tree(query.get("q", [""])[0], int(query.get("limit", ["300"])[0])))
        elif route.path == "/api/v1/repository/graph":
            self.server.latest_snapshot()
            self._json(HTTPStatus.OK, self.server.collector.graph())
        elif route.path == "/api/v1/repository/file":
            self._repository_file(query.get("path", [""])[0])
        elif route.path == "/api/v1/issues":
            self._json(HTTPStatus.OK, {"issues": self.server.latest_snapshot().get("incidents", [])})
        elif route.path.startswith("/api/v1/issues/"):
            issue_id = route.path.removeprefix("/api/v1/issues/")
            issues = self.server.latest_snapshot().get("incidents", [])
            issue = next((item for item in issues if item.get("issue_id") == issue_id), None)
            self._json(HTTPStatus.OK if issue else HTTPStatus.NOT_FOUND, issue or {"error": "ISSUE_NOT_FOUND"})
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def _repository_file(self, rel: str):
        path = PurePosixPath(rel)
        if not rel or path.is_absolute() or ".." in path.parts or SENSITIVE_PATH_RE.search(path.as_posix()):
            self._json(HTTPStatus.FORBIDDEN, {"error": "PATH_BLOCKED"})
            return
        self.server.latest_snapshot()
        entry_paths = {item.get("path") for item in self.server.collector.tree(limit=MAX_TREE_ITEMS).get("entries", []) if isinstance(item, dict)}
        normalized = path.as_posix()
        if normalized not in entry_paths:
            self._json(HTTPStatus.NOT_FOUND, {"error": "FILE_NOT_TRACKED"})
            return
        target = (ROOT / Path(*path.parts)).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            self._json(HTTPStatus.FORBIDDEN, {"error": "PATH_BLOCKED"})
            return
        try:
            if target.stat().st_size > 100_000:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "FILE_TOO_LARGE"})
                return
            source = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "FILE_NOT_TEXT"})
            return
        source = redact_text(source, 100_000)
        self._json(HTTPStatus.OK, {"path": normalized, "source": source, "analysis": "SOURCE_DERIVED", "repository_sha": self.server.latest_snapshot().get("repository", {}).get("local_sha")})

    def do_POST(self):
        if not self._host_valid() or not self._origin_valid():
            self._json(HTTPStatus.BAD_REQUEST, {"error": "ORIGIN_BLOCKED"})
            return
        route = urlparse(self.path).path
        if route == "/api/v1/auth/login":
            if not self._authenticated():
                self._json(HTTPStatus.FORBIDDEN, {"error": "WINDOWS_LOCAL_USER_REQUIRED"})
                return
            cookie = self.server.auth_store.session_cookie()
            self._json(HTTPStatus.OK, {"authenticated": True}, {"Set-Cookie": f"{SESSION_NAME}={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_SECONDS}"})
            return
        if not self._require_auth():
            return
        if route == "/api/v1/auth/logout":
            self._json(HTTPStatus.OK, {"authenticated": False}, {"Set-Cookie": f"{SESSION_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
        elif route == "/api/v1/refresh":
            self._json(HTTPStatus.OK, self.server.latest_snapshot(refresh=True))
        elif route == "/api/v1/issues/export":
            try:
                body = self._body()
            except (ValueError, UnicodeError, json.JSONDecodeError):
                self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_REQUEST"})
                return
            issue_id = body.get("issue_id")
            issue = next((item for item in self.server.latest_snapshot().get("incidents", []) if item.get("issue_id") == issue_id), None)
            if not issue:
                self._json(HTTPStatus.NOT_FOUND, {"error": "ISSUE_NOT_FOUND"})
                return
            try:
                package = export_issue_package(issue)
            except (OSError, ValueError) as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": redact_text(exc, 200)})
                return
            self._json(HTTPStatus.CREATED, package)
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def do_OPTIONS(self):
        self._json(HTTPStatus.METHOD_NOT_ALLOWED, {"error": "METHOD_NOT_ALLOWED"})


def main():
    if os.name != "nt":
        raise SystemExit("This deployment uses Windows local-process authentication and is Windows-only.")
    server = DashboardServer((HOST, PORT), Handler)
    print(f"Angel FNO Evidence Dashboard listening at http://{HOST}:{PORT}/")
    print("Bound to loopback only. Windows process SID auth enabled. No broker order or cloud write APIs are enabled.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
