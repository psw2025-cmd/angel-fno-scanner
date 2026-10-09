#!/usr/bin/env python3
"""
tools/invisible_pattern_finder.py
100-Year Autonomy Audit — Invisible Pattern Finder
Scans codebase, git history, and runtime references to identify:
1. Timestamp validation bypasses (falling back to wall-clock, omitting exchange verification)
2. Hardcoded flags ('1' or '0') that bypass conditional safety gates
3. Workflow failure patterns and fragile concurrency races
Outputs docs/100_year_local_audit/invisible_complexity_report.json
"""

import os
import re
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "docs" / "100_year_local_audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUTPUT_DIR / "invisible_complexity_report.json"

def scan_timestamp_bypasses():
    bypasses = []
    # Patterns where system wall clock is used instead of exchange tick timestamp
    wall_clock_patterns = [
        (re.compile(r"datetime\.(?:datetime\.)?now\(.*?\)\.strftime"), "System clock used as data timestamp instead of exchFeedTime"),
        (re.compile(r"time\.time\(\)"), "Epoch wall clock comparison without exchange time alignment"),
        (re.compile(r"raw\.get\(['\"]exchFeedTime['\"]\)\s*or\s*raw\.get\(['\"]exchTradeTime['\"]\)\s*or\s*['\"]['\"]"), "Fallback to empty string on missing exchange feed time"),
        (re.compile(r"stamped\s*=\s*now\.strftime"), "Scanner stamped with host wall-clock rather than earliest tick"),
    ]

    for root, _, files in os.walk(REPO_ROOT):
        if any(ignored in root for ignored in [".git", ".venv", "__pycache__", "docs/100_year_local_audit", "scratch"]):
            continue
        for f in files:
            if f.endswith(".py"):
                fpath = Path(root) / f
                rel_path = fpath.relative_to(REPO_ROOT).as_posix()
                try:
                    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for idx, line in enumerate(lines, 1):
                        for pat, desc in wall_clock_patterns:
                            if pat.search(line):
                                bypasses.append({
                                    "file": rel_path,
                                    "line": idx,
                                    "snippet": line.strip()[:140],
                                    "issue_type": "TIMESTAMP_BYPASS",
                                    "description": desc,
                                    "risk": "HIGH: Allows stale data to be published as fresh if exchange data freezes"
                                })
                except Exception:
                    pass
    return bypasses

def scan_hardcoded_flags():
    hardcoded = []
    flag_patterns = [
        (re.compile(r"ALLOW_PRODUCTION_WRITES['\"]?\s*[:=]\s*['\"]1['\"]"), "ALLOW_PRODUCTION_WRITES hardcoded to 1"),
        (re.compile(r"['\"]ALLOW_PRODUCTION_WRITES['\"]\s*,\s*['\"]1['\"]"), "ALLOW_PRODUCTION_WRITES hardcoded to 1"),
        (re.compile(r"MAX_RUNTIME_SECONDS['\"]?\s*[:=]\s*['\"](?:22500|24300)['\"]"), "Hardcoded unbounded market runtime without check-in circuit breaker"),
        (re.compile(r"cancel-in-progress:\s*false"), "Concurrent workflow run cancellation disabled"),
    ]

    for root, _, files in os.walk(REPO_ROOT):
        if any(ignored in root for ignored in [".git", ".venv", "__pycache__", "docs/100_year_local_audit", "scratch"]):
            continue
        for f in files:
            if f.endswith(".py") or f.endswith(".yml") or f.endswith(".yaml") or f.endswith(".ps1"):
                fpath = Path(root) / f
                rel_path = fpath.relative_to(REPO_ROOT).as_posix()
                try:
                    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for idx, line in enumerate(lines, 1):
                        for pat, desc in flag_patterns:
                            if pat.search(line):
                                hardcoded.append({
                                    "file": rel_path,
                                    "line": idx,
                                    "snippet": line.strip()[:140],
                                    "issue_type": "HARDCODED_SAFETY_FLAG",
                                    "description": desc,
                                    "risk": "MEDIUM: May bypass dry-run isolation or execute unauthorized writes"
                                })
                except Exception:
                    pass
    return hardcoded

def scan_workflow_runs():
    cmd = ["gh", "run", "list", "--workflow", "market_bot.yml", "--limit", "25", "--json", "databaseId,status,conclusion,createdAt,event,headSha"]
    runs = []
    try:
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout.strip():
            runs = json.loads(res.stdout.strip())
    except Exception as e:
        runs = [{"error": str(e)}]
    return runs

def main():
    print("[100-YEAR AUDIT] Running Invisible Pattern Finder...")
    bypasses = scan_timestamp_bypasses()
    hardcoded = scan_hardcoded_flags()
    runs = scan_workflow_runs()

    report = {
        "audit_version": "100_YEAR_AUTONOMY_V1",
        "generated_at_utc": subprocess.check_output(["python", "-c", "import datetime; print(datetime.datetime.now(datetime.timezone.utc).isoformat())"], text=True).strip(),
        "summary": {
            "timestamp_bypasses_count": len(bypasses),
            "hardcoded_flags_count": len(hardcoded),
            "analyzed_workflow_runs_count": len(runs),
        },
        "invisible_timestamp_bypasses": bypasses,
        "hardcoded_safety_flags": hardcoded,
        "recent_workflow_runs": runs,
        "architectural_recommendations": [
            "1. Enforce strict EXCHANGE_VERIFIED requirement on every quote before acceptance (no wall-clock fallbacks).",
            "2. Make ALLOW_PRODUCTION_WRITES strictly conditional on valid exchange timestamp freshness within 90 seconds.",
            "3. Enforce pre-push git rebase lock to prevent snapshot push race collisions.",
            "4. Separate fetch, validate, and publish into 3 isolated pure layers with circuit breakers."
        ]
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"[OK] Saved invisible complexity report to {REPORT_FILE}")
    print(f"     Found {len(bypasses)} timestamp bypasses, {len(hardcoded)} hardcoded safety flags.")

if __name__ == "__main__":
    main()
