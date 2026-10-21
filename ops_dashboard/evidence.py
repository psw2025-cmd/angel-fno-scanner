"""Read-only local evidence collectors for the private operations dashboard."""
from __future__ import annotations

import ast
import datetime as dt
import itertools
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import threading
import time
import zipfile
from typing import Any

ROOT = Path(os.environ.get("ANGEL_FNO_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
SUPERVISOR_ROOT = Path(os.environ.get("ANGEL_SUPERVISOR_ROOT", r"C:\AngelFNO_Workstation\angel-agent-supervisor"))
APP_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AngelFNO" / "dashboard"
EVIDENCE_ROOT = APP_ROOT / "evidence"
EXPORT_ROOT = APP_ROOT / "exports"
REPOSITORY = "psw2025-cmd/angel-fno-scanner"
TELEMETRY_FILE = ROOT / "system_live_telemetry.json"
FRESH_SECONDS = 300
RETENTION_DAYS = 30
MAX_FILE_BYTES = 256_000
MAX_GRAPH_FILES = 1600
MAX_GRAPH_SOURCE_BYTES = 80_000_000
MAX_TREE_ITEMS = 6000
MAX_GRAPH_NODES = 700
MAX_GRAPH_EDGES = 1400
SECRET_KEY_RE = re.compile(r"(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|private[_-]?key|bearer)\s*[:=]\s*([^\s,;]+)")
SECRET_VALUE_RE = re.compile(r"(?i)(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|Bearer\s+[A-Za-z0-9._~+/-]{12,})")
SENSITIVE_PATH_RE = re.compile(r"(?i)(^|/)(\.env[^/]*|secrets?(?:/.*)?|[^/]*(?:credential|secret)[^/]*\.(?:json|ya?ml|toml|txt)|[^/]+\.pem|[^/]+\.key|auth\.json)$")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "backups", "scratch", "data", ".tmp.drivedownload", ".tmp.driveupload"}
PY_SUFFIXES = {".py"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def redact_text(value: Any, limit: int = 600) -> str:
    text = str(value or "")
    text = SECRET_VALUE_RE.sub("[REDACTED]", text)
    text = SECRET_KEY_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", text)
    return text[:limit]


def sanitize(value: Any, key: str = "") -> Any:
    if re.search(r"(?i)(token|secret|password|credential|private.?key|authorization|client.?email|email)", key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items() if not re.search(r"(?i)(token|secret|password|credential|private.?key|authorization|client.?email|email)", str(k))}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(value)


def run_readonly(args: list[str], *, cwd: Path = ROOT, timeout: float = 8.0, max_bytes: int = 1_000_000) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            env={**os.environ, "NO_COLOR": "1", "GIT_TERMINAL_PROMPT": "0"},
        )
        out = proc.stdout[:max_bytes]
        err = redact_text(proc.stderr, 1000)
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "stdout": out, "stderr": err}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": "TIMEOUT"}
    except OSError as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": type(exc).__name__}


def _json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return default


def _git(*args: str, timeout: float = 6.0) -> dict[str, Any]:
    return run_readonly(["git", *args], cwd=ROOT, timeout=timeout)


def _parse_timestamp(value: Any) -> dt.datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def telemetry_observation() -> dict[str, Any]:
    if not TELEMETRY_FILE.is_file():
        return {"health": "UNKNOWN", "freshness": "UNKNOWN", "collection": "ERROR", "source": "system_live_telemetry.json", "error": "Telemetry file not found", "nodes": []}
    try:
        data = json.loads(TELEMETRY_FILE.read_text(encoding="utf-8"))
        file_stat = TELEMETRY_FILE.stat()
    except (OSError, ValueError, UnicodeError) as exc:
        return {"health": "UNKNOWN", "freshness": "UNKNOWN", "collection": "ERROR", "source": "system_live_telemetry.json", "error": type(exc).__name__, "nodes": []}
    observed_at = dt.datetime.fromtimestamp(file_stat.st_mtime, tz=dt.timezone.utc)
    age = max(0, int((dt.datetime.now(dt.timezone.utc) - observed_at).total_seconds()))
    freshness = "FRESH" if age <= FRESH_SECONDS else "STALE"
    nodes = []
    for node_id, raw in (data.get("nodes") or {}).items():
        if not isinstance(raw, dict):
            continue
        source_status = str(raw.get("status", "UNKNOWN")).upper()
        # A stale report is historical evidence, never current health.
        current_health = source_status if freshness == "FRESH" and source_status in {"PASS", "FAIL", "UNKNOWN"} else "UNKNOWN"
        if freshness == "FRESH" and source_status == "HEALTHY":
            current_health = "PASS"
        elif freshness == "FRESH" and source_status in {"CRITICAL", "FAILED", "ERROR"}:
            current_health = "FAIL"
        nodes.append({
            "id": str(node_id),
            "name": redact_text(raw.get("name", node_id), 100),
            "reported_health": source_status,
            "health": current_health,
            "freshness": freshness,
            "collection": "OK",
            "source_timestamp": redact_text(raw.get("last_checked", ""), 80) or None,
            "observation_age_seconds": age,
            "diagnostics": redact_text(raw.get("diagnostics", ""), 300),
        })
    return {
        "health": "UNKNOWN" if freshness == "STALE" else str(data.get("system_state", "UNKNOWN")),
        "freshness": freshness,
        "collection": "OK",
        "source": "system_live_telemetry.json",
        "file_observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "embedded_generated_at": redact_text(data.get("generated_at", ""), 80) or None,
        "age_seconds": age,
        "reported_system_state": redact_text(data.get("system_state", "UNKNOWN"), 120),
        "nodes": nodes,
        "note": "Stale file contents are historical; displayed current health is UNKNOWN.",
    }


def local_runtime_observation() -> dict[str, Any]:
    ps = r"$names=@('PBIDesktop.exe','msmdsrv.exe','agy.exe','codex.exe','claude.exe','python.exe'); Get-CimInstance Win32_Process | Where-Object { $names -contains $_.Name } | Select-Object Name,ProcessId,CreationDate | ConvertTo-Json -Compress"
    process_result = run_readonly(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=5, max_bytes=100_000)
    processes: list[dict[str, Any]] = []
    if process_result["ok"] and process_result["stdout"].strip():
        try:
            raw = json.loads(process_result["stdout"])
            if isinstance(raw, dict):
                raw = [raw]
            processes = [{"name": str(item.get("Name", "")), "pid": int(item.get("ProcessId", 0)), "started": str(item.get("CreationDate", ""))} for item in raw if isinstance(item, dict)]
        except (ValueError, TypeError):
            processes = []
    by_name: dict[str, list[dict[str, Any]]] = {}
    for item in processes:
        by_name.setdefault(item["name"].lower(), []).append(item)
    return {
        "health": "UNKNOWN",
        "freshness": "FRESH" if process_result["ok"] else "UNKNOWN",
        "collection": "OK" if process_result["ok"] else "ERROR",
        "observed_at": utc_now(),
        "processes": processes,
        "powerbi": {"health": "UNKNOWN", "desktop_pids": [x["pid"] for x in by_name.get("pbidesktop.exe", [])], "engine_pids": [x["pid"] for x in by_name.get("msmdsrv.exe", [])], "note": "Process presence does not prove model freshness or successful rendering."},
        "agents": {name.removesuffix(".exe"): len(by_name.get(name, [])) for name in ("agy.exe", "codex.exe", "claude.exe")},
    }


def repository_identity() -> dict[str, Any]:
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    status = _git("status", "--porcelain=v1", "--untracked-files=normal")
    origin = _git("ls-remote", "origin", "refs/heads/main", timeout=8)
    local_sha = head["stdout"].strip() if head["ok"] else None
    origin_sha = origin["stdout"].split()[0] if origin["ok"] and origin["stdout"].split() else None
    return {
        "health": "UNKNOWN",
        "collection": "OK" if head["ok"] else "ERROR",
        "observed_at": utc_now(),
        "branch": branch["stdout"].strip() if branch["ok"] else "UNKNOWN",
        "local_sha": local_sha,
        "origin_main_sha": origin_sha,
        "local_matches_origin_main": (local_sha == origin_sha) if local_sha and origin_sha and (branch["stdout"].strip() == "main" if branch["ok"] else False) else None,
        "dirty": bool(status["stdout"].strip()) if status["ok"] else None,
        "changed_paths": [redact_text(line[3:], 240) for line in status["stdout"].splitlines()[:100] if len(line) >= 4 and not SENSITIVE_PATH_RE.search(line[3:].replace("\\", "/"))],
        "runtime_sha": None,
        "runtime_sha_status": "UNKNOWN_NOT_EXPOSED_BY_CONFIGURED_LOCAL_SOURCES",
        "error": None if head["ok"] else head["stderr"],
    }


def github_observation() -> dict[str, Any]:
    repo_meta = run_readonly(["gh", "api", f"repos/{REPOSITORY}", "--jq", "{default_branch: .default_branch, private: .private, updated_at: .updated_at}"], timeout=8, max_bytes=20_000)
    runs = run_readonly(["gh", "run", "list", "--repo", REPOSITORY, "--limit", "20", "--json", "databaseId,workflowName,status,conclusion,headSha,createdAt,updatedAt"], timeout=10, max_bytes=100_000)
    prs = run_readonly(["gh", "pr", "list", "--repo", REPOSITORY, "--state", "open", "--limit", "50", "--json", "number,title,headRefName,headRefOid,baseRefOid,mergeStateStatus,reviewDecision,updatedAt"], timeout=10, max_bytes=100_000)
    errors = [x["stderr"] for x in (repo_meta, runs, prs) if not x["ok"]]
    try:
        metadata = json.loads(repo_meta["stdout"]) if repo_meta["ok"] else None
        workflow_runs = json.loads(runs["stdout"]) if runs["ok"] else []
        pull_requests = json.loads(prs["stdout"]) if prs["ok"] else []
    except ValueError:
        metadata, workflow_runs, pull_requests = None, [], []
        errors.append("Invalid JSON from GitHub CLI")
    for run in workflow_runs:
        run["health"] = "PASS" if run.get("conclusion") == "success" else "FAIL" if run.get("conclusion") == "failure" else "UNKNOWN"
    return {
        "health": "UNKNOWN",
        "freshness": "FRESH" if not errors else "UNKNOWN",
        "collection": "ERROR" if errors else "OK",
        "observed_at": utc_now(),
        "metadata": metadata,
        "workflow_runs": workflow_runs[:20],
        "open_pull_requests": pull_requests[:50],
        "error": "; ".join(redact_text(e, 200) for e in errors) if errors else None,
    }


def _safe_tracked_paths() -> list[str]:
    result = _git("ls-files", "-z", timeout=8)
    if not result["ok"]:
        return []
    paths = []
    for raw in result["stdout"].split("\x00"):
        rel = raw.replace("\\", "/").strip()
        if not rel or SENSITIVE_PATH_RE.search(rel):
            continue
        if any(part in SKIP_DIRS for part in PurePosixPath(rel).parts):
            continue
        if rel.startswith(".env") or "/.env" in rel:
            continue
        paths.append(rel)
    return paths[:MAX_TREE_ITEMS]


def repository_tree(query: str = "", limit: int = 300) -> dict[str, Any]:
    paths = _safe_tracked_paths()
    q = query.casefold().strip()[:120]
    if q:
        paths = [p for p in paths if q in p.casefold()]
    limit = max(1, min(int(limit), 1000))
    entries = []
    for rel in paths[:limit]:
        p = ROOT / Path(*PurePosixPath(rel).parts)
        try:
            st = p.stat()
        except OSError:
            continue
        suffix = p.suffix.lower()
        entries.append({"path": rel, "kind": "notebook" if suffix == ".ipynb" else "code" if suffix == ".py" else "workflow" if ".github/workflows/" in rel else "config" if suffix in {".json", ".yml", ".yaml", ".toml"} else "document" if suffix in {".md", ".rst", ".txt"} else "asset", "size_bytes": st.st_size, "supported_analysis": suffix in {".py", ".md", ".json", ".yml", ".yaml", ".toml", ".html", ".js", ".css"}})
    return {"observed_at": utc_now(), "count": len(entries), "total_matching": len(paths), "truncated": len(paths) > limit, "entries": entries}


def _module_to_path(module: str, source_path: str, known: set[str]) -> str | None:
    if not module:
        return None
    candidates = [module.replace(".", "/") + ".py", module.replace(".", "/") + "/__init__.py"]
    parent = str(PurePosixPath(source_path).parent)
    if module.startswith("."):
        rel = module.lstrip(".").replace(".", "/")
        candidates = [f"{parent}/{rel}.py", f"{parent}/{rel}/__init__.py"]
    for candidate in candidates:
        normalized = str(PurePosixPath(candidate))
        if normalized in known:
            return normalized
    return None


def repository_graph() -> dict[str, Any]:
    paths = [p for p in _safe_tracked_paths() if p.endswith(".py")][:MAX_GRAPH_FILES]
    known = set(paths)
    nodes = []
    edges: list[dict[str, str]] = []
    function_index: dict[str, list[tuple[str, str]]] = {}
    parsed_sources: dict[str, str] = {}
    parsed = 0
    unsupported = 0
    bytes_scanned = 0
    for rel in paths:
        p = ROOT / Path(*PurePosixPath(rel).parts)
        try:
            file_size = p.stat().st_size
            if file_size > MAX_FILE_BYTES or bytes_scanned + file_size > MAX_GRAPH_SOURCE_BYTES:
                unsupported += 1
                continue
            source = p.read_text(encoding="utf-8")
            bytes_scanned += file_size
            tree = ast.parse(source, filename=rel)
        except (OSError, UnicodeError, SyntaxError):
            unsupported += 1
            continue
        parsed += 1
        parsed_sources[rel] = source
        nodes.append({"id": rel, "kind": "file", "source": "SOURCE_DERIVED"})
        imported = set()
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                imported.update(alias.name for alias in item.names)
            elif isinstance(item, ast.ImportFrom):
                module = item.module or ""
                if item.level:
                    module = "." * item.level + module
                imported.add(module)
        for module in imported:
            target = _module_to_path(module, rel, known)
            if target and target != rel:
                edges.append({"from": rel, "to": target, "relationship": "imports", "source": "SOURCE_DERIVED"})
        for item in ast.walk(tree):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(item, ast.ClassDef) else "function"
                full = f"{rel}::{item.name}"
                nodes.append({"id": full, "kind": kind, "source": "SOURCE_DERIVED"})
                function_index.setdefault(item.name, []).append((rel, full))
    # Bounded conservative intra-repository call edges: only resolve globally unique names.
    for rel, source in parsed_sources.items():
        try:
            tree = ast.parse(source, filename=rel)
        except SyntaxError:
            continue
        for item in ast.walk(tree):
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller = f"{rel}::{item.name}"
                for call in (x for x in ast.walk(item) if isinstance(x, ast.Call)):
                    if isinstance(call.func, ast.Name):
                        refs = function_index.get(call.func.id, [])
                        if len(refs) == 1 and refs[0][0] == rel and refs[0][1] != caller:
                            edges.append({"from": caller, "to": refs[0][1], "relationship": "calls", "source": "SOURCE_DERIVED"})
    nodes = nodes[:MAX_GRAPH_NODES]
    ids = {n["id"] for n in nodes}
    unique = []
    seen = set()
    for edge in edges:
        if edge["from"] not in ids or edge["to"] not in ids:
            continue
        key = (edge["from"], edge["to"], edge["relationship"])
        if key not in seen:
            unique.append(edge)
            seen.add(key)
        if len(unique) >= MAX_GRAPH_EDGES:
            break
    return {"observed_at": utc_now(), "relationship_type": "SOURCE_DERIVED", "files_seen": len(paths), "files_parsed": parsed, "unsupported": unsupported, "source_bytes_scanned": bytes_scanned, "nodes": nodes, "edges": unique, "truncated": len(paths) >= MAX_GRAPH_FILES or len(nodes) >= MAX_GRAPH_NODES or len(unique) >= MAX_GRAPH_EDGES or bytes_scanned >= MAX_GRAPH_SOURCE_BYTES}


def history_hotspots(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(int(limit), 250))
    result = _git("log", f"-{limit}", "--format=%H%x09%cI", "--name-only", "--", timeout=10)
    if not result["ok"]:
        return {"health": "UNKNOWN", "collection": "ERROR", "error": result["stderr"], "commits": [], "hotspots": [], "coupling": []}
    commits = []
    path_counts: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    current = None
    names: list[str] = []
    def flush() -> None:
        nonlocal current, names
        if not current:
            return
        unique = sorted(set(names))
        commits.append({"sha": current[0], "committed_at": current[1], "paths": unique[:100]})
        for path in unique:
            path_counts[path] = path_counts.get(path, 0) + 1
        for left, right in itertools.combinations(unique[:80], 2):
            pair_counts[(left, right)] = pair_counts.get((left, right), 0) + 1
        current, names = None, []
    for line in result["stdout"].splitlines():
        if "\t" in line and re.fullmatch(r"[0-9a-f]{40}\t.+", line):
            flush()
            current = line.split("\t", 1)
        elif line.strip() and current and not line.startswith(" "):
            names.append(line.strip())
        elif line.strip() and not current and re.fullmatch(r"[0-9a-f]{40}\t.+", line):
            current = line.split("\t", 1)
    flush()
    hotspots = [
        {"path": path, "commits": count, "relationship": "HISTORY_CORRELATED"}
        for path, count in sorted(path_counts.items(), key=lambda item: (-item[1], item[0]))[:100]
    ]
    coupling = [
        {"left": pair[0], "right": pair[1], "cochange_commits": count, "relationship": "HISTORY_CORRELATED"}
        for pair, count in sorted(pair_counts.items(), key=lambda item: (-item[1], item[0]))[:100]
    ]
    return {"health": "PASS", "collection": "OK", "observed_at": utc_now(),
            "window_commits": len(commits), "hotspots": hotspots,
            "coupling": coupling, "commits": commits}


def _supervisor_state() -> dict[str, Any]:
    state = _json_file(SUPERVISOR_ROOT / "state.json", {})
    tasks = []
    for task in state.get("tasks", []) if isinstance(state, dict) else []:
        if not isinstance(task, dict):
            continue
        tasks.append({"id": redact_text(task.get("id", ""), 100), "status": redact_text(task.get("status", "UNKNOWN"), 80), "attempts": task.get("attempts"), "last_error": redact_text(task.get("last_error", ""), 300), "started_at": redact_text(task.get("started_at", ""), 80)})
    return {"health": "UNKNOWN", "freshness": "UNKNOWN", "collection": "OK" if state else "ERROR", "updated": redact_text(state.get("updated", ""), 80) if state else None, "tasks": tasks, "source": "local_supervisor_state", "runtime_sha": None}


class SnapshotStore:
    def __init__(self, root: Path = EVIDENCE_ROOT, retention_days: int = RETENTION_DAYS):
        self.root = root
        self.retention_days = retention_days
        self.lock = threading.Lock()

    def append(self, snapshot: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now(dt.timezone.utc)
        target = self.root / f"snapshots-{now:%Y-%m-%d}.jsonl"
        compact = dict(snapshot)
        tree = compact.pop("repository_tree", {})
        graph = compact.pop("dependency_graph", {})
        history = compact.pop("history", {})
        compact["analysis_summary"] = compact.get("analysis_summary") or {
            "tracked_paths_seen": tree.get("total_matching"),
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "history_window_commits": history.get("window_commits"),
        }
        line = json.dumps(sanitize(compact), ensure_ascii=True, separators=(",", ":")) + "\n"
        with self.lock:
            if target.exists() and target.stat().st_size > 16_000_000:
                return
            with target.open("a", encoding="utf-8") as stream:
                stream.write(line)
            cutoff = now - dt.timedelta(days=self.retention_days)
            for path in self.root.glob("snapshots-*.jsonl"):
                try:
                    day = dt.date.fromisoformat(path.stem.removeprefix("snapshots-"))
                    if dt.datetime.combine(day, dt.time.max, tzinfo=dt.timezone.utc) < cutoff:
                        path.unlink()
                except (OSError, ValueError):
                    continue

    def recent(self, limit: int = 500) -> list[dict[str, Any]]:
        files = sorted(self.root.glob("snapshots-*.jsonl"))[-max(1, min(limit, 31)):]
        rows = []
        total_bytes = 0
        for path in files:
            try:
                if total_bytes >= 8_000_000:
                    break
                with path.open("r", encoding="utf-8") as stream:
                    for line in stream:
                        total_bytes += len(line)
                        if total_bytes >= 8_000_000:
                            break
                        if line.strip():
                            rows.append(json.loads(line))
            except (OSError, ValueError):
                continue
        return rows[-max(1, min(limit, 5000)):]


class EvidenceCollector:
    def __init__(self, store: SnapshotStore | None = None):
        self.store = store or SnapshotStore()
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, Any]] = {}
        self._last_snapshot: dict[str, Any] | None = None
        self._incident_first_seen: dict[str, str] = {}
        self._repo_tree: dict[str, Any] = {"entries": [], "count": 0, "total_matching": 0, "truncated": False}
        self._dependency_graph: dict[str, Any] = {"nodes": [], "edges": [], "files_seen": 0, "files_parsed": 0, "unsupported": 0}
        self._history_analysis: dict[str, Any] = {"hotspots": [], "coupling": [], "commits": [], "window_commits": 0}
        for prior in self.store.recent(1000):
            for issue in prior.get("incidents", []) if isinstance(prior, dict) else []:
                issue_id = issue.get("issue_id") if isinstance(issue, dict) else None
                first_seen = issue.get("first_seen") if isinstance(issue, dict) else None
                if issue_id and first_seen:
                    self._incident_first_seen.setdefault(issue_id, first_seen)

    def _cached(self, key: str, ttl: float, function):
        now = time.monotonic()
        entry = self._cache.get(key)
        if entry and now - entry[0] < ttl:
            return entry[1]
        value = function()
        self._cache[key] = (now, value)
        return value

    def _incidents(self, telemetry: dict[str, Any], github: dict[str, Any], supervisor: dict[str, Any], repo: dict[str, Any]) -> list[dict[str, Any]]:
        now = utc_now()
        raw: list[dict[str, Any]] = []
        if telemetry.get("freshness") == "STALE":
            raw.append({"issue_id": "LOCAL-TELEMETRY-STALE", "severity": "high", "title": "Local telemetry snapshot is stale", "observed_impact": "The monitor file is older than the freshness threshold; reported service labels are historical, not current health.", "affected_entities": ["system_live_telemetry.json"], "source_references": ["system_live_telemetry.json"], "reproduction_status": "OBSERVED_FILE_AGE", "root_cause_status": "UNKNOWN", "competing_hypotheses": ["collector is stopped", "collector cannot authenticate", "collector output path drifted"], "prerequisite_steps": ["verify collector process and output path", "collect a new read-only snapshot"], "proposed_correction": "Restore the authorized read-only collector; preserve UNKNOWN until a fresh observation is recorded.", "verification_tests": ["file timestamp advances", "freshness age is recomputed from file mtime", "source node statuses match observed evidence"], "rollback": "No production change; disable collector and retain last snapshot as stale history.", "approval_requirements": "None for local read-only diagnosis; credential changes require owner action.", "remaining_unknowns": ["collector identity", "runtime SHA", "fresh Google service responses"]})
        failures = [r for r in github.get("workflow_runs", []) if r.get("conclusion") == "failure"]
        for run in failures[:10]:
            issue_id = f"GITHUB-RUN-{run.get('databaseId')}"
            raw.append({"issue_id": issue_id, "severity": "high", "title": f"Workflow failed: {run.get('workflowName', 'unknown workflow')}", "observed_impact": f"GitHub reports conclusion=failure on head {str(run.get('headSha',''))[:12]}.", "affected_entities": ["GitHub Actions", str(run.get("workflowName", ""))], "source_references": ["GitHub Actions read-only API"], "reproduction_status": "REMOTE_RUN_RECORDED", "root_cause_status": "UNKNOWN", "competing_hypotheses": ["test failure", "provider outage", "workflow environment drift"], "prerequisite_steps": ["inspect exact run logs", "compare run head SHA with current main"], "proposed_correction": "Inspect the failed job and fix only the confirmed cause.", "verification_tests": ["rerun affected workflow on same SHA", "verify latest conclusion and head SHA"], "rollback": "Revert only the isolated correction if focused validation regresses.", "approval_requirements": "Review required before merge or deployment.", "remaining_unknowns": ["job-level failed step", "runtime/deployed SHA"]})
        for task in supervisor.get("tasks", []):
            if task.get("status") in {"WAITING_FOR_AGENT", "QUARANTINED", "RETRY_PENDING", "FAILED_TASK"}:
                raw.append({"issue_id": f"SUPERVISOR-{task.get('id','UNKNOWN')}", "severity": "medium", "title": f"Supervisor task blocked: {task.get('id','unknown')}", "observed_impact": redact_text(task.get("last_error", "Task is blocked."), 300), "affected_entities": ["Angel supervisor", str(task.get("id", ""))], "source_references": ["local state.json"], "reproduction_status": "OBSERVED_LOCAL_STATE", "root_cause_status": "UNKNOWN", "competing_hypotheses": ["agent provider availability", "stale task state", "runner or worktree lifecycle failure"], "prerequisite_steps": ["inspect task-specific logs", "verify eligible agent preflight"], "proposed_correction": "Run bounded isolated diagnosis and preserve the original task allowlist.", "verification_tests": ["task runner result recorded", "agent artifact boundary checked"], "rollback": "Preserve worktree and evidence; do not reset unknown files.", "approval_requirements": "Use only the existing task approval and allowlist.", "remaining_unknowns": ["exact agent output", "task worktree identity"]})
        if repo.get("local_matches_origin_main") is False:
            raw.append({"issue_id": "REPOSITORY-SHA-DRIFT", "severity": "medium", "title": "Local main differs from origin/main", "observed_impact": "Current checkout and remote main resolve to different commits.", "affected_entities": ["Git main", "origin/main"], "source_references": ["git rev-parse", "git ls-remote"], "reproduction_status": "OBSERVED_SHA_COMPARISON", "root_cause_status": "UNKNOWN", "competing_hypotheses": ["local branch behind/ahead", "fetch unavailable"], "prerequisite_steps": ["inspect exact divergence without reset"], "proposed_correction": "Review ancestry and working-tree state before any pull/rebase.", "verification_tests": ["remote/local SHA and ancestry recorded"], "rollback": "No ref changes performed by dashboard.", "approval_requirements": "Approval required before merge/push.", "remaining_unknowns": ["deployed runtime SHA"]})
        for issue in raw:
            self._incident_first_seen.setdefault(issue["issue_id"], now)
            issue.update({"first_seen": self._incident_first_seen[issue["issue_id"]], "last_seen": now, "observation_window": "current collector observation", "repository_sha": repo.get("local_sha"), "runtime_sha_if_known": repo.get("runtime_sha"), "suspected_impact": "Impact beyond the recorded observation has not been proven.", "evidence_references": issue["source_references"]})
        return raw

    def collect(self, *, persist: bool = True, force_remote: bool = False) -> dict[str, Any]:
        with self._lock:
            telemetry = telemetry_observation()
            runtime = local_runtime_observation()
            repo = self._cached("repo", 15, repository_identity)
            github = self._cached("github", 60 if not force_remote else 0, github_observation)
            supervisor = _supervisor_state()
            from ops_dashboard.cloud_reads import collect_cloud
            cloud = self._cached("cloud", 120 if not force_remote else 0, lambda: collect_cloud(ROOT))
            tree = self._cached("tree", 180, lambda: repository_tree(limit=MAX_TREE_ITEMS))
            graph = self._cached("graph", 300, repository_graph)
            history = self._cached("history", 300, lambda: history_hotspots(100))
            self._repo_tree = tree
            self._dependency_graph = graph
            self._history_analysis = history
            observed = utc_now()
            snapshot = {
                "schema_version": "1.0.0",
                "observed_at": observed,
                "repository": repo,
                "runtime": runtime,
                "telemetry": telemetry,
                "github": github,
                "supervisor": supervisor,
                "cloud_observations": cloud,
                "analysis_summary": {"tracked_paths": tree.get("total_matching"), "graph_nodes": len(graph.get("nodes", [])), "graph_edges": len(graph.get("edges", [])), "history_commits": history.get("window_commits"), "unsupported_python_files": graph.get("unsupported")},
                "coverage": [
                    {"source": "local_git", "health": repo.get("health", "UNKNOWN"), "freshness": "FRESH", "collection": repo.get("collection", "UNKNOWN"), "evidence": "local checkout"},
                    {"source": "origin_main", "health": "PASS" if repo.get("origin_main_sha") else "UNKNOWN", "freshness": "FRESH" if repo.get("origin_main_sha") else "UNKNOWN", "collection": "OK" if repo.get("origin_main_sha") else "ERROR", "evidence": "git ls-remote"},
                    {"source": "github_actions", "health": github.get("health", "UNKNOWN"), "freshness": github.get("freshness", "UNKNOWN"), "collection": github.get("collection", "UNKNOWN"), "evidence": "gh CLI read-only"},
                    {"source": "local_telemetry_file", "health": telemetry.get("health", "UNKNOWN"), "freshness": telemetry.get("freshness", "UNKNOWN"), "collection": telemetry.get("collection", "UNKNOWN"), "evidence": telemetry.get("source")},
                    {"source": "local_processes", "health": runtime.get("health", "UNKNOWN"), "freshness": runtime.get("freshness", "UNKNOWN"), "collection": runtime.get("collection", "UNKNOWN"), "evidence": "name/PID/creation-time only"},
                    cloud["bigquery_live"],
                    cloud["google_sheets_live"],
                    {"source": "powerbi_model_freshness", "health": "UNKNOWN", "freshness": "UNKNOWN", "collection": "BLOCKED", "evidence": runtime.get("powerbi", {}).get("note")},
                    {"source": "deployed_runtime_sha", "health": "UNKNOWN", "freshness": "UNKNOWN", "collection": "BLOCKED", "evidence": repo.get("runtime_sha_status")},
                ],
            }
            snapshot["incidents"] = self._incidents(telemetry, github, supervisor, repo)
            snapshot = sanitize(snapshot)
            if persist:
                self.store.append(snapshot)
            self._last_snapshot = snapshot
            return snapshot

    def get_latest(self) -> dict[str, Any]:
        if self._last_snapshot is None:
            return self.collect()
        return self._last_snapshot

    def history(self, limit: int = 250) -> dict[str, Any]:
        rows = self.store.recent(limit)
        return {"count": len(rows), "snapshots": rows, "history": self._history_analysis}

    def tree(self, query: str = "", limit: int = 300) -> dict[str, Any]:
        q = query.casefold().strip()[:120]
        bounded_limit = max(1, min(int(limit), 1000))
        entries = self._repo_tree.get("entries", [])
        if q:
            entries = [entry for entry in entries if q in entry.get("path", "").casefold()]
        return {**self._repo_tree, "count": len(entries[:bounded_limit]), "entries": entries[:bounded_limit], "truncated": len(entries) > bounded_limit}

    def graph(self) -> dict[str, Any]:
        return self._dependency_graph


def redact_issue_package(issue: dict[str, Any]) -> dict[str, Any]:
    allowed = {"issue_id", "severity", "first_seen", "last_seen", "observation_window", "repository_sha", "runtime_sha_if_known", "affected_entities", "source_references", "evidence_references", "reproduction_status", "root_cause_status", "competing_hypotheses", "observed_impact", "suspected_impact", "prerequisite_steps", "proposed_correction", "verification_tests", "rollback", "approval_requirements", "remaining_unknowns", "title"}
    return sanitize({key: issue.get(key) for key in allowed if key in issue})


def export_issue_package(issue: dict[str, Any]) -> dict[str, Any]:
    issue = redact_issue_package(issue)
    issue_id = str(issue.get("issue_id", ""))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", issue_id):
        raise ValueError("Invalid issue ID")
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = EXPORT_ROOT / f"{issue_id}-{timestamp}"
    target.mkdir(parents=True, exist_ok=False)
    issue_json = json.dumps(issue, indent=2, ensure_ascii=True)
    files = {
        "issue.json": issue_json,
        "affected_paths.json": json.dumps({"paths": issue.get("affected_entities", []), "source_references": issue.get("source_references", [])}, indent=2),
        "evidence_manifest.json": json.dumps({"schema_version": "1.0.0", "issue_id": issue_id, "created_at": utc_now(), "repository_sha": issue.get("repository_sha"), "runtime_sha_if_known": issue.get("runtime_sha_if_known"), "references": issue.get("evidence_references", []), "redaction": "secrets filtered by dashboard exporter"}, indent=2),
        "reproduction.md": "# Reproduction\n\n" + str(issue.get("reproduction_status", "UNKNOWN")) + "\n\n" + "\n".join(f"- {redact_text(x, 300)}" for x in issue.get("prerequisite_steps", [])),
        "proposed_solution.md": "# Proposed correction\n\n" + redact_text(issue.get("proposed_correction", "Not proposed"), 2000) + "\n\n# Rollback\n\n" + redact_text(issue.get("rollback", "Not specified"), 1000),
        "verification_plan.md": "# Verification plan\n\n" + "\n".join(f"- {redact_text(x, 500)}" for x in issue.get("verification_tests", [])) + "\n\n# Approval requirements\n\n" + redact_text(issue.get("approval_requirements", "Unknown"), 1000),
        "agent_prompt.txt": "Inspect this evidence package only. Do not modify source, production data, credentials, or deployment. Reproduce the issue in an isolated fixture; distinguish observation from hypothesis; propose a minimal patch and regression test; wait for approval before external writes.\n\nIssue: " + issue_id + "\nRepository SHA: " + str(issue.get("repository_sha") or "UNKNOWN") + "\nEvidence references: " + ", ".join(issue.get("evidence_references", [])),
    }
    for name, content in files.items():
        path = target / name
        path.write_text(content + ("\n" if not content.endswith("\n") else ""), encoding="utf-8")
    hashes = {path.name: __import__("hashlib").sha256(path.read_bytes()).hexdigest() for path in target.iterdir() if path.is_file()}
    (target / "manifest.sha256.json").write_text(json.dumps({"algorithm": "SHA-256", "files": hashes}, indent=2), encoding="utf-8")
    archive = target / f"{target.name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(target.iterdir()):
            if path.is_file() and path != archive:
                bundle.write(path, arcname=path.name)
    history = EXPORT_ROOT / "export-history.jsonl"
    history.parent.mkdir(parents=True, exist_ok=True)
    with history.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"issue_id": issue_id, "created_at": utc_now(), "package": target.name, "files": sorted(files)}) + "\n")
    return {"package": target.name, "files": sorted([*files, "manifest.sha256.json"]), "created_at": utc_now(), "download_url": f"/api/v1/exports/{target.name}.zip"}
