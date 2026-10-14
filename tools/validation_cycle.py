"""Read-only startup checks for the Mumbai validation job.

This path never publishes paper results and never places broker orders.
"""
from __future__ import annotations

import json
import os
import re

from gainers import GAINER_ROW_LIMIT
from tools.cycle_provenance import resolve_git_sha, resolve_run_id
from tools.publication_lease import LIVE_ORDER_FLAGS, lease_script
from universe_contract import EXPECTED_FNO_UNIVERSE_COUNT

_SECRET = re.compile(r"(?i)(token|jwt|secret|password|pin|totp|api[_-]?key|private_key)(['\"\s:=]+)[^\s,}'\"]+")


def public_error(exc: BaseException) -> str:
    text = _SECRET.sub(r"\1\2[REDACTED]", str(exc))
    return text[:400]


def run_validation() -> int:
    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("startup", "PASS", "validation process started")
    writes = (os.getenv("ALLOW_PRODUCTION_WRITES") or "0").strip()
    live = [flag for flag in LIVE_ORDER_FLAGS if (os.getenv(flag) or "0").strip() == "1"]
    if writes == "1" or live:
        add("paper_writes_off", "FAIL", "production writes or live-order flags are enabled")
    else:
        add("paper_writes_off", "PASS", "ALLOW_PRODUCTION_WRITES is not 1 and live-order flags are off")

    try:
        run_id = resolve_run_id()
        git_sha = resolve_git_sha()
        add("provenance", "PASS", f"run_id={run_id} git_sha={git_sha}")
    except Exception as exc:
        add("provenance", "FAIL", public_error(exc))
        run_id = ""
        git_sha = ""

    image = os.getenv("VALIDATION_IMAGE_DIGEST", "").strip()
    add(
        "image_identity",
        "PASS" if git_sha and image.startswith("sha256:") else "FAIL",
        f"source_commit={git_sha or 'missing'} image_digest={image or 'not injected'}",
    )
    sql = lease_script()
    add(
        "publication_lease",
        "PASS" if "BEGIN TRANSACTION" in sql and "transaction_write_lock" in sql else "FAIL",
        "atomic lease script is present; not executed because production writes are off",
    )
    add(
        "ranking_contract",
        "PASS" if GAINER_ROW_LIMIT == 200 and EXPECTED_FNO_UNIVERSE_COUNT == 219 else "FAIL",
        f"universe={EXPECTED_FNO_UNIVERSE_COUNT} ranking_rows={GAINER_ROW_LIMIT}",
    )

    try:
        import scanner
        api = scanner.angel_login()
        add("auth", "PASS", "Angel session started; no order method called")
        universe = scanner.discover_universe(api)
        count = len(universe)
        add(
            "canonical_symbols",
            "PASS" if count == 219 else "FAIL",
            f"verified futures={count}",
        )
        from gainers import market_is_open, select_ranked, quote_from_angel
        now = scanner.now_ist()
        tokens = [meta["token"] for meta in universe.values()]
        quotes, failures = scanner.fetch_chunked(api, tokens)
        from tools.exchange_timestamp import oldest_exchange_timestamp
        oldest = oldest_exchange_timestamp(list(quotes.values())) if quotes else "none"
        if market_is_open(now) and quotes and not failures:
            freshness = "PASS"
        else:
            freshness = "FAIL"
        add(
            "data_freshness",
            freshness,
            f"now_ist={now.isoformat()} market_open={market_is_open(now)} oldest_exchange_timestamp={oldest} quote_failures={failures} quotes={len(quotes)}",
        )
        ranked = []
        for meta in universe.values():
            raw = quotes.get(meta["token"])
            if not raw:
                continue
            try:
                ranked.append(quote_from_angel(raw, meta))
            except Exception:
                continue
        selected = select_ranked([item for item in ranked if item is not None])
        ranking_ok = market_is_open(now) and 0 < len(selected) <= 200
        add(
            "ranking",
            "PASS" if ranking_ok else "FAIL",
            f"ranked_rows={len(selected)} limit=200 market_open={market_is_open(now)}",
        )
    except Exception as exc:
        add("auth_or_market_data", "FAIL", public_error(exc))

    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF)
        add("resource_use", "PASS", f"max_rss_kb={usage.ru_maxrss}")
    except Exception as exc:
        add("resource_use", "PASS", f"resource module unavailable: {public_error(exc)}")

    failed = [item for item in checks if item["status"] != "PASS"]
    report = {"mode": "validation", "publish": False, "broker_orders": False, "checks": checks}
    print(json.dumps(report, indent=2))
    return 1 if failed else 0
