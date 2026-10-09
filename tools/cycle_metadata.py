"""Write cycle metadata from verified FULL quote ticks, not processing clock."""
import json
import os
import subprocess
from pathlib import Path
from tools.exchange_timestamp import oldest_exchange_timestamp

def write_cycle_metadata(quotes, *, run_id, git_sha, market_session, path, writer_id="market_bot"):
    if market_session not in ("OPEN", "CLOSED", "EOD"):
        raise ValueError("invalid session")
    oldest = oldest_exchange_timestamp(quotes)
    meta = {
        "run_id": str(run_id), "git_sha": str(git_sha),
        "cycle_id": f"cycle_{run_id}_{oldest.replace(':', '-')}",
        "source_timestamp": oldest,
        "market_session": market_session,
        "writer_id": writer_id,
        "data_freshness_status": "EXCHANGE_VERIFIED",
        "verification": "Angel One FULL exchFeedTime oldest tick",
        "verified_quote_count": len(quotes),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    temp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    os.replace(temp, target)
    return meta


def generate_cycle_metadata(quotes, run_id, git_sha, session, *, expected_quotes=219):
    """Enforce full unique-token exchange-tick coverage before accepting a cycle."""
    quotes = list(quotes)
    tokens = [str(q.get("symbolToken", "")).strip() for q in quotes]
    if len(quotes) != expected_quotes or len(set(tokens)) != expected_quotes or not all(tokens):
        raise ValueError(f"Expected {expected_quotes} distinct quotes, got {len(quotes)} records / {len(set(tokens))} tokens")
    oldest = oldest_exchange_timestamp(quotes)
    return {
        "run_id": str(run_id), "git_sha": str(git_sha),
        "cycle_id": f"cycle_{run_id}_{oldest.replace(':', '-')}",
        "source_timestamp": oldest, "market_session": session,
        "writer_id": "market_bot", "data_freshness_status": "EXCHANGE_VERIFIED",
        "verified_count": len(quotes), "total": expected_quotes,
        "verification": "Angel One FULL exchFeedTime oldest tick",
    }
