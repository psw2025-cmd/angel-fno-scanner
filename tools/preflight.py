"""One-command read-only preflight for agents.

Collects git, Cloud Run, Scheduler, BigQuery and Sheet evidence into one JSON
file and evaluates it against fail-closed rules.  Nothing is mutated.

Usage:
    python tools/preflight.py [--out PATH] [--skip-sheet] [--skip-cloud]

Exit code 0 only when no check is FAIL.  Checks that could not be measured are
NOT_PROVEN and never count as PASS.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = "fno-angel-prod-1790444589"
REGION = "asia-south1"
JOB = "angel-market-scan-job"
TABLE = "fno_predictions.option_predictions_live"
REQUIRED_PROVENANCE = (
    "cycle_id",
    "data_freshness_status",
    "git_sha",
    "run_id",
    "source_timestamp",
    "writer_id",
)
SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
EXPECTED_SYMBOLS = 219

PASS, FAIL, NOT_PROVEN = "PASS", "FAIL", "NOT_PROVEN"


def _run(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, shell=(sys.platform == "win32")
        )
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    except Exception as exc:  # measurement failure is reported, never hidden
        return 1, f"{type(exc).__name__}: {exc}"


def _json_cmd(cmd: list[str]):
    code, out = _run(cmd)
    if code != 0:
        return None, out.strip()[-300:]
    try:
        return json.loads(out), ""
    except ValueError as exc:
        return None, f"bad json: {exc}"


def collect_git(repo: Path) -> dict:
    head = _run(["git", "-C", str(repo), "rev-parse", "HEAD"])[1].strip()
    remote = _run(["git", "-C", str(repo), "ls-remote", "origin", "refs/heads/main"])[1].split()
    return {"head": head, "remote_main": remote[0] if remote else None}


def collect_job() -> dict:
    data, err = _json_cmd(
        ["gcloud", "run", "jobs", "describe", JOB, "--region", REGION, "--project", PROJECT, "--format", "json"]
    )
    if data is None:
        return {"error": err}
    tpl = data["spec"]["template"]["spec"]["template"]["spec"]
    container = tpl["containers"][0]
    env = {e["name"]: e["value"] for e in container.get("env", []) if "value" in e}
    execs, _ = _json_cmd(
        ["gcloud", "run", "jobs", "executions", "list", "--job", JOB, "--region", REGION,
         "--project", PROJECT, "--limit", "3", "--format", "json"]
    )
    latest = []
    for item in execs or []:
        status = item.get("status", {})
        latest.append({
            "name": item["metadata"]["name"],
            "running": status.get("runningCount", 0),
            "succeeded": status.get("succeededCount", 0),
            "failed": status.get("failedCount", 0),
        })
    return {
        "image": container["image"],
        "timeout_seconds": int(tpl.get("timeoutSeconds", 0) or 0),
        "env": env,
        "executions": latest,
    }


def collect_scheduler() -> dict:
    data, err = _json_cmd(
        ["gcloud", "scheduler", "jobs", "list", "--location", REGION, "--project", PROJECT, "--format", "json"]
    )
    if data is None:
        return {"error": err}
    return {j["name"].rsplit("/", 1)[-1]: j.get("state") for j in data}


def collect_bigquery() -> dict:
    table, err = _json_cmd(["bq", f"--project_id={PROJECT}", f"--location={REGION}", "show", "--format=json", TABLE])
    if table is None:
        return {"error": err}
    cols = [f["name"] for f in table["schema"]["fields"]]
    sql = (
        "SELECT COUNT(*) n, COUNT(DISTINCT symbol) syms, COUNTIF(git_sha IS NOT NULL) git_sha_nonnull "
        f"FROM {TABLE}"
    )
    rows, err2 = _json_cmd(
        ["bq", f"--project_id={PROJECT}", f"--location={REGION}", "query", "--nouse_legacy_sql", "--format=json", sql]
    )
    out = {"columns": cols, "last_modified_ms": table.get("lastModifiedTime")}
    if rows:
        out.update({k: int(v) for k, v in rows[0].items()})
    else:
        out["query_error"] = err2
    return out


def collect_sheet() -> dict:
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import credentials  # type: ignore
        import gspread  # type: ignore

        gc = gspread.service_account_from_dict(credentials.load_service_account())
        ws = gc.open_by_key(credentials.get_canonical_sheet_id()).worksheet("Formula Checks")
        rows = ws.get("A1:E12")
        return {"gates": {r[0]: r[4] for r in rows if len(r) >= 5 and r[0]}}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"[:300]}


def evaluate(ev: dict) -> list[dict]:
    """Pure rule evaluation over collected evidence (unit-tested)."""
    checks: list[dict] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    git = ev.get("git") or {}
    if git.get("head") and git.get("remote_main"):
        add("git_head_recorded", PASS, f"head={git['head'][:12]} remote_main={git['remote_main'][:12]}")
    else:
        add("git_head_recorded", NOT_PROVEN, "could not read HEAD or remote main")

    job = ev.get("job")
    if not job or "error" in job:
        add("job_described", NOT_PROVEN, (job or {}).get("error", "skipped"))
    else:
        add("job_image_digest_pinned", PASS if "@sha256:" in job["image"] else FAIL, job["image"][-80:])
        env = job["env"]
        timeout = job["timeout_seconds"]
        budget = int(env.get("MAX_RUNTIME_SECONDS", "0") or 0)
        ok = bool(timeout) and 0 < budget <= timeout - 300
        add("runtime_budget_below_platform_timeout", PASS if ok else FAIL, f"MAX_RUNTIME_SECONDS={budget} timeout={timeout}")
        gsha = env.get("GIT_SHA")
        if gsha is None:
            add("git_sha_env_not_placeholder", PASS, "unset; image bakes SOURCE_COMMIT")
        else:
            add("git_sha_env_not_placeholder", PASS if SHA_RE.match(gsha) else FAIL, f"GIT_SHA={gsha}")
        running = [e["name"] for e in job["executions"] if e["running"]]
        add("running_executions", PASS, ",".join(running) if running else "none")

    sched = ev.get("scheduler")
    if not sched or "error" in sched:
        add("scheduler_listed", NOT_PROVEN, (sched or {}).get("error", "skipped"))
    else:
        add("scheduler_states_recorded", PASS, json.dumps(sched, sort_keys=True))

    bq = ev.get("bigquery")
    if not bq or "error" in bq:
        add("bigquery_table", NOT_PROVEN, (bq or {}).get("error", "skipped"))
    else:
        missing = [c for c in REQUIRED_PROVENANCE if c not in bq["columns"]]
        add("provenance_columns_present", PASS if not missing else FAIL, "missing=" + ",".join(missing) if missing else "all 6 present")
        if "n" in bq:
            add("universe_complete", PASS if bq["n"] == bq["syms"] == EXPECTED_SYMBOLS else FAIL,
                f"rows={bq['n']} symbols={bq['syms']} expected={EXPECTED_SYMBOLS}")
            add("rows_have_git_sha", PASS if bq["git_sha_nonnull"] == bq["n"] else FAIL,
                f"git_sha non-null {bq['git_sha_nonnull']}/{bq['n']}")
        else:
            add("universe_complete", NOT_PROVEN, bq.get("query_error", ""))

    sheet = ev.get("sheet")
    if not sheet or "error" in sheet:
        add("sheet_gates", NOT_PROVEN, (sheet or {}).get("error", "skipped"))
    else:
        failing = sorted(g for g, s in sheet["gates"].items() if s in ("FAIL", "BLOCKED", "RANK LAYER BLOCKED"))
        add("sheet_gates", FAIL if failing else PASS, "failing=" + ",".join(failing) if failing else "no failing gates")
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-sheet", action="store_true")
    ap.add_argument("--skip-cloud", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(__file__).resolve().parents[1]
    now = datetime.now(timezone.utc)
    ev: dict = {"collected_at_utc": now.isoformat(), "git": collect_git(repo)}
    if not args.skip_cloud:
        ev["job"] = collect_job()
        ev["scheduler"] = collect_scheduler()
        ev["bigquery"] = collect_bigquery()
    if not args.skip_sheet:
        ev["sheet"] = collect_sheet()
    checks = evaluate(ev)
    report = {"evidence": ev, "checks": checks, "overall": FAIL if any(c["status"] == FAIL for c in checks) else (
        NOT_PROVEN if any(c["status"] == NOT_PROVEN for c in checks) else PASS)}
    out = Path(args.out) if args.out else repo / "preflight-output" / f"preflight_{now:%Y%m%d_%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for c in checks:
        print(f"{c['status']:<10} {c['check']}: {c['detail']}")
    print(f"OVERALL {report['overall']}  evidence={out}")
    return 1 if report["overall"] == FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
