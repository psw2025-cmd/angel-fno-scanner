#!/usr/bin/env python3
"""Free-tier LangSmith tracing for the Angel F&O paper scanner.

The Developer plan includes 5,000 base traces per month (14-day retention) and
stops there until a payment card is added. This module stays inside that plan:

- one base-retention trace per interval, addressed to the agent environment
- a per-host monthly cap that cannot be configured above 4,500
- rule-based feedback only (no model evaluator)
- publication already finished before a trace is attempted

Paid actions are refused in code. There is no environment switch that turns them on.
"""

import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:  # pragma: no cover - Python 3.9+ has zoneinfo
    IST = timezone.utc

DEFAULT_ENDPOINT = "https://api.smith.langchain.com"
DEFAULT_AGENT_ID = "angel-fno"
DEFAULT_ENVIRONMENT = "local"
DEFAULT_PROJECT = "angel-fno"
DEFAULT_MONTHLY_CAP = 2000
HARD_MONTHLY_CAP = 4500
DEFAULT_MIN_INTERVAL_SECONDS = 900
REQUEST_TIMEOUT_SECONDS = 8
RETENTION = "base_14d"

PAID_FEATURES_BLOCKED = (
    {
        "id": "payment_card",
        "reason": "Adding a card removes the 5,000-trace stop and enables pay-as-you-go.",
    },
    {
        "id": "extended_retention",
        "reason": "Extended retention is a separate billable trace upgrade (180 days).",
    },
    {
        "id": "retention_automation",
        "reason": "An automation that matches a run upgrades the whole trace to extended retention.",
    },
    {
        "id": "anthropic_or_other_llm",
        "reason": "The deepagents quickstart calls a model provider and that provider bills the call.",
    },
    {
        "id": "langsmith_deployment",
        "reason": "Managed deployments bill compute. Dedicated deployments bill while idle.",
    },
    {
        "id": "plus_or_enterprise_plan",
        "reason": "Plus is a paid seat plan. Enterprise is a paid contract.",
    },
    {
        "id": "dataset_export",
        "reason": "Dataset copies persist indefinitely and are left as a manual governance choice.",
    },
)

MANUAL_OPERATOR_STEPS = (
    "Leave the LangSmith project retention on Base (14 days).",
    "Do not add a payment card on the Billing page.",
    "Do not create an automation rule from the + New menu.",
    "Do not run the deepagents quickstart and do not set ANTHROPIC_API_KEY for it.",
    "Put LANGSMITH_* values in the shell environment or a gitignored .env. The loader does not override variables that are already set.",
)

_SECRET_TEXT = re.compile(r"lsv2_[A-Za-z0-9_]+|sk-ant-[A-Za-z0-9_\-]+|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----")
_SENSITIVE_KEY = re.compile(r"(api[_-]?key|secret|password|token|pin|totp|authorization|credential)", re.I)
_AGENT_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class PaidFeatureBlocked(RuntimeError):
    """Raised when a caller asks for a feature that can create a bill."""


def refuse_paid(action):
    """Refuse a paid LangSmith or model-provider action. No override exists."""
    known = {item["id"]: item["reason"] for item in PAID_FEATURES_BLOCKED}
    reason = known.get(action, "This action is outside the free Developer plan.")
    raise PaidFeatureBlocked("%s: %s" % (action, reason))


def uuid7():
    """Time-ordered id recommended by the LangSmith run API."""
    unix_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return uuid.UUID(int=value)


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _monthly_cap(environ):
    raw = str(environ.get("LANGSMITH_MONTHLY_TRACE_CAP", "")).strip()
    if not raw:
        return DEFAULT_MONTHLY_CAP
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MONTHLY_CAP
    return max(0, min(value, HARD_MONTHLY_CAP))


def _interval_seconds(environ):
    raw = str(environ.get("LANGSMITH_MIN_INTERVAL_SECONDS", "")).strip()
    if not raw:
        return DEFAULT_MIN_INTERVAL_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MIN_INTERVAL_SECONDS
    return max(0, value)


def _budget_path(environ):
    raw = str(environ.get("LANGSMITH_BUDGET_PATH", "")).strip()
    if raw:
        return Path(raw)
    return Path.home() / ".angel_fno" / "langsmith_free_budget.json"


def ist_month(now=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    try:
        return current.astimezone(IST).strftime("%Y-%m")
    except Exception:
        return current.astimezone(timezone.utc).strftime("%Y-%m")


def load_config(environ=None):
    if environ is None:
        from credentials import load_env
        load_env()
        environ = os.environ
    agent_id = str(environ.get("LANGSMITH_AGENT_ID", "")).strip() or DEFAULT_AGENT_ID
    environment = str(environ.get("LANGSMITH_AGENT_ENVIRONMENT", "")).strip() or DEFAULT_ENVIRONMENT
    project = str(environ.get("LANGSMITH_PROJECT", "")).strip() or agent_id or DEFAULT_PROJECT
    endpoint = str(environ.get("LANGSMITH_ENDPOINT", "")).strip() or DEFAULT_ENDPOINT
    return {
        "tracing": _truthy(environ.get("LANGSMITH_TRACING")),
        "endpoint": endpoint.rstrip("/"),
        "api_key": str(environ.get("LANGSMITH_API_KEY", "")).strip(),
        "agent_id": agent_id,
        "environment": environment,
        "project": project,
        "monthly_cap": _monthly_cap(environ),
        "min_interval_seconds": _interval_seconds(environ),
        "budget_path": _budget_path(environ),
    }


def agent_address(config):
    agent_id = config.get("agent_id") or ""
    environment = config.get("environment") or ""
    if not (_AGENT_TOKEN.match(agent_id) and _AGENT_TOKEN.match(environment)):
        return ""
    return "lrn:agents/%s/environments/%s" % (agent_id, environment)


def redact(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if _SENSITIVE_KEY.search(str(key)):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET_TEXT.sub("[REDACTED]", value)
    return value


def contains_secret(value):
    try:
        blob = json.dumps(value, default=str, sort_keys=True)
    except TypeError:
        blob = str(value)
    return _SECRET_TEXT.search(blob) is not None


def summarize_cycle(predictions, reconciliation, next_day_picks, ist_str):
    """Compact cycle record. Headlines, URLs, and credentials stay out of the trace."""
    rows = list(predictions or [])
    ranked = sorted(rows, key=lambda row: row.get("rank", 10 ** 9))[:5]
    leaders = []
    for row in ranked:
        leaders.append({
            "symbol": row.get("symbol"),
            "rank": row.get("rank"),
            "bias": row.get("directional_bias"),
            "ce_win_prob": row.get("ce_win_prob"),
            "pe_win_prob": row.get("pe_win_prob"),
            "intensity": row.get("intensity_score"),
            "gap_pct": row.get("expected_gap_pct"),
            "gap_direction": row.get("gap_direction"),
            "illiquid": bool(row.get("is_illiquid")),
        })
    recon = reconciliation if isinstance(reconciliation, dict) else {}
    picks = next_day_picks if isinstance(next_day_picks, dict) else {}
    summary = {
        "inputs": {
            "cycle_ist": ist_str,
            "symbol_count": len(rows),
            "illiquid_count": sum(1 for row in rows if row.get("is_illiquid")),
        },
        "outputs": {
            "top": leaders,
            "reconciliation": {
                "cycle": recon.get("cycle"),
                "hit_rate_pct": recon.get("hit_rate_pct"),
                "recall_at_10": recon.get("recall_at_10"),
                "mean_rank": recon.get("mean_rank"),
                "hits_count": recon.get("hits_count"),
                "misses_count": recon.get("misses_count"),
            },
            "next_day_pick_counts": {
                "ce": len(picks.get("top_ce_picks") or []),
                "pe": len(picks.get("top_pe_picks") or []),
            },
            "paper_mode": True,
            "live_orders": 0,
        },
    }
    return summary


def evaluate_free_tier(summary):
    outputs = summary.get("outputs") or {}
    leaders = outputs.get("top") or []
    checks = {
        "live_orders_off": outputs.get("live_orders") == 0,
        "paper_mode": outputs.get("paper_mode") is True,
        "bounded_leaders": len(leaders) <= 5,
        "no_secret_material": not contains_secret(summary),
    }
    return {
        "key": "free_tier_contract",
        "score": 1.0 if all(checks.values()) else 0.0,
        "checks": checks,
    }


def _read_budget(path, month, cap):
    if not path.exists():
        return {"month": month, "traces_sent": 0, "last_sent_epoch": 0, "cap": cap}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("month") != month:
        return {"month": month, "traces_sent": 0, "last_sent_epoch": 0, "cap": cap}
    try:
        sent = int(data.get("traces_sent", 0))
        last = float(data.get("last_sent_epoch", 0))
    except (TypeError, ValueError):
        return None
    return {"month": month, "traces_sent": max(0, sent), "last_sent_epoch": last, "cap": cap}


def _write_budget(path, budget):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(budget, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _safe_text(text, api_key):
    cleaned = text or ""
    if api_key:
        cleaned = cleaned.replace(api_key, "[REDACTED]")
    cleaned = _SECRET_TEXT.sub("[REDACTED]", cleaned)
    return cleaned[:300]


class RequestsTransport:
    def __init__(self, api_key, timeout=REQUEST_TIMEOUT_SECONDS):
        self._api_key = api_key
        self._timeout = timeout

    def __call__(self, request):
        import requests
        response = requests.request(
            request["method"],
            request["url"],
            json=request["payload"],
            headers={
                "X-API-Key": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=self._timeout,
        )
        return {"status_code": response.status_code, "text": response.text}


def _post(config, payload, transport):
    url = config["endpoint"] + "/api/v1/runs"
    request = {"method": "POST", "url": url, "payload": payload}
    if transport is None:
        transport = RequestsTransport(config["api_key"])
    try:
        result = transport(request)
    except Exception as exc:
        return {"ok": False, "status": "transport_error", "detail": type(exc).__name__}
    code = int(result.get("status_code", 0))
    detail = _safe_text(str(result.get("text", "")), config.get("api_key"))
    if code in (200, 202):
        return {"ok": True, "status_code": code, "detail": detail}
    return {"ok": False, "status_code": code, "detail": detail, "status": "rejected"}


def _feedback(config, run_id, key, score, comment, transport):
    payload = {
        "id": str(uuid7()),
        "run_id": run_id,
        "key": key,
        "score": score,
        "comment": comment,
    }
    url = config["endpoint"] + "/api/v1/feedback"
    request = {"method": "POST", "url": url, "payload": payload}
    if transport is None:
        transport = RequestsTransport(config["api_key"])
    try:
        result = transport(request)
    except Exception as exc:
        return {"key": key, "score": score, "accepted": False, "detail": type(exc).__name__}
    code = int(result.get("status_code", 0))
    return {
        "key": key,
        "score": score,
        "accepted": code in (200, 201, 202),
        "status_code": code,
    }


def _run_payload(config, name, summary, run_id, start, address=None, project=None):
    body = {
        "id": run_id,
        "name": name,
        "run_type": "chain",
        "inputs": summary["inputs"],
        "outputs": summary["outputs"],
        "start_time": start,
        "end_time": start,
        "tags": ["paper", "free-tier", "base-retention", "env:%s" % config["environment"]],
        "extra": {
            "metadata": {
                "agent_id": config["agent_id"],
                "agent_environment": config["environment"],
                "retention_tier": RETENTION,
                "billing": "none",
                "paper_mode": "1",
                "live_order_authority": "0",
                "source": "angel-fno-scanner",
            }
        },
    }
    if address:
        body["address"] = address
    if project:
        body["session_name"] = project
    return body


def trace_prediction_cycle(predictions, reconciliation, next_day_picks, ist_str, transport=None, force=False, now=None, name="angel_fno_prediction_cycle", environ=None):
    """Send one base-tier trace, or return a no-send status. Never raises for I/O."""
    config = load_config(environ)
    raw_summary = summarize_cycle(predictions, reconciliation, next_day_picks, ist_str)
    summary = redact(raw_summary)
    evaluation = evaluate_free_tier(summary)
    if contains_secret(raw_summary):
        evaluation = {
            "key": "free_tier_contract",
            "score": 0.0,
            "checks": {"no_secret_material": False},
        }
    result = {
        "status": "disabled",
        "retention": RETENTION,
        "billing": "none",
        "address": agent_address(config),
        "project": config["project"],
        "monthly_cap": config["monthly_cap"],
        "min_interval_seconds": config["min_interval_seconds"],
        "evaluation": evaluation,
        "paid_features_blocked": [item["id"] for item in PAID_FEATURES_BLOCKED],
    }
    if not config["tracing"]:
        return result
    if not config["api_key"]:
        result["status"] = "skipped_no_key"
        return result
    if not result["address"]:
        result["status"] = "contract_failed"
        result["detail"] = "agent_id_or_environment_rejected"
        return result
    if evaluation["score"] != 1.0 or contains_secret(raw_summary) or contains_secret(summary):
        result["status"] = "contract_failed"
        return result

    month = ist_month(now)
    budget = _read_budget(config["budget_path"], month, config["monthly_cap"])
    if budget is None:
        result["status"] = "budget_unreadable"
        return result
    result["traces_sent_this_month"] = budget["traces_sent"]
    if budget["traces_sent"] >= config["monthly_cap"]:
        result["status"] = "budget_exhausted"
        return result
    current_epoch = (now or datetime.now(timezone.utc)).timestamp()
    elapsed = current_epoch - float(budget.get("last_sent_epoch") or 0)
    if not force and elapsed < config["min_interval_seconds"]:
        result["status"] = "sampled_out"
        return result

    run_id = str(uuid7())
    start = datetime.now(timezone.utc).isoformat()
    primary = _run_payload(config, name, summary, run_id, start, address=result["address"])
    sent = _post(config, primary, transport)
    used_address = True
    if (not sent["ok"]) and sent.get("status_code") == 403:
        fallback = _run_payload(config, name, summary, run_id, start, project=config["project"])
        sent = _post(config, fallback, transport)
        used_address = False
    if not sent["ok"]:
        result["status"] = sent.get("status") or "rejected"
        result["http_status"] = sent.get("status_code")
        result["detail"] = sent.get("detail")
        return result

    budget["traces_sent"] += 1
    budget["last_sent_epoch"] = current_epoch
    budget["last_run_id"] = run_id
    budget["cap"] = config["monthly_cap"]
    try:
        _write_budget(config["budget_path"], budget)
    except OSError:
        result["status"] = "budget_unwritable"
        result["run_id"] = run_id
        return result

    feedback = [
        _feedback(config, run_id, "paper_safety", 1.0, "PAPER mode and live orders 0", transport),
        _feedback(config, run_id, "free_tier_contract", 1.0, "Base retention, bounded payload, no secrets", transport),
    ]
    result.update({
        "status": "sent",
        "run_id": run_id,
        "address_used": used_address,
        "traces_sent_this_month": budget["traces_sent"],
        "feedback": feedback,
    })
    return result


def status_report(environ=None, now=None):
    config = load_config(environ)
    month = ist_month(now)
    budget = _read_budget(config["budget_path"], month, config["monthly_cap"]) or {
        "traces_sent": None,
        "last_sent_epoch": None,
    }
    if config["tracing"] and config["api_key"]:
        state = "ready"
    elif config["tracing"]:
        state = "skipped_no_key"
    else:
        state = "disabled"
    return {
        "status": state,
        "tracing_requested": config["tracing"],
        "key_present": bool(config["api_key"]),
        "endpoint": config["endpoint"],
        "agent_id": config["agent_id"],
        "agent_environment": config["environment"],
        "project": config["project"],
        "address": agent_address(config),
        "retention": RETENTION,
        "billing": "none",
        "monthly_cap": config["monthly_cap"],
        "hard_monthly_cap": HARD_MONTHLY_CAP,
        "traces_sent_this_month": budget.get("traces_sent"),
        "min_interval_seconds": config["min_interval_seconds"],
        "paid_features_blocked": [item["id"] for item in PAID_FEATURES_BLOCKED],
        "manual_operator_steps": list(MANUAL_OPERATOR_STEPS),
    }


def _emit_json(payload, json_only):
    text = json.dumps(payload, sort_keys=True)
    stream = sys.stdout if json_only else sys.stdout
    stream.write(text + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="LangSmith free-tier tracing status and one smoke trace")
    parser.add_argument("--status", action="store_true", help="Print redacted free-tier status")
    parser.add_argument("--smoke", action="store_true", help="Send one base-tier smoke trace")
    parser.add_argument("--json-only", action="store_true", help="Write one JSON document to stdout")
    args = parser.parse_args(argv)
    if not args.status and not args.smoke:
        args.status = True
    if args.smoke:
        payload = trace_prediction_cycle(
            predictions=[{
                "symbol": "SMOKE",
                "rank": 1,
                "directional_bias": "NEUTRAL",
                "ce_win_prob": 50.0,
                "pe_win_prob": 50.0,
                "intensity_score": 35,
                "expected_gap_pct": 0.0,
                "gap_direction": "FLAT / NEUTRAL OPEN",
                "is_illiquid": False,
            }],
            reconciliation={"cycle": 0, "hit_rate_pct": 0.0, "recall_at_10": 0.0, "mean_rank": 0.0, "hits_count": 0, "misses_count": 0},
            next_day_picks={"top_ce_picks": [], "top_pe_picks": []},
            ist_str=datetime.now(timezone.utc).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            force=True,
            name="angel_fno_free_tier_smoke",
        )
        # Drop the evaluation checks map from the public smoke document only when it is huge.
        public = {key: value for key, value in payload.items() if key != "evaluation"}
        public["evaluation_score"] = payload.get("evaluation", {}).get("score")
        _emit_json(public, args.json_only)
        return 0 if payload.get("status") in {"sent", "disabled", "skipped_no_key", "sampled_out"} else 1
    _emit_json(status_report(), args.json_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
