"""Cloud PAPER orchestration, delegating calculation to reviewed Phase 2 code."""
import argparse
import hashlib
import math
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_runner.session import validate_environment, REQUIRED
from cloud_runner.health import snapshot

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "proof-output" / "cloud-paper"
CHILD_TIMEOUT_SECONDS = 600  # Bound a stuck child below the 20-minute CI job limit.

def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()

def exact_paper_flags(data):
    """JSON safety flags must be integer 1/0, never Python bool equivalents."""
    return (type(data.get("paper_mode")) is int
            and data["paper_mode"] == 1
            and type(data.get("live_order_authority")) is int
            and data["live_order_authority"] == 0
            # Older Phase 2 artifacts lack this field. Absence is not
            # independent proof of zero orders; reject explicit contradictions.
            and ("real_broker_orders" not in data
                 or (type(data["real_broker_orders"]) is int
                     and data["real_broker_orders"] == 0)))


def validate_prediction_ranking(payload):
    """Reject absent, duplicate, or non-tradeable PAPER forecast contracts.

    This is a structural check only, not proof of market prices or broker fills.
    """
    ranking = payload.get("ranking") if isinstance(payload, dict) else None
    if not isinstance(ranking, list) or not ranking:
        raise RuntimeError("PREDICTION_RANKING_EMPTY")
    seen = set()
    for expected_rank, row in enumerate(ranking, 1):
        if not isinstance(row, dict) or type(row.get("rank")) is not int or row["rank"] != expected_rank:
            raise RuntimeError("PREDICTION_RANKING_INVALID")
        if (not isinstance(row.get("symbol"), str) or not row["symbol"].strip()
                or not isinstance(row.get("tradingsymbol"), str) or not row["tradingsymbol"].strip()
                or not isinstance(row.get("symboltoken"), str) or not row["symboltoken"].isdigit()
                or row.get("option_type") not in ("CE", "PE")):
            raise RuntimeError("PREDICTION_RANKING_INVALID")
        try:
            date.fromisoformat(row["expiry"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("PREDICTION_RANKING_INVALID") from exc
        strike = row.get("strike")
        if type(strike) not in (int, float) or not math.isfinite(strike) or strike <= 0:
            raise RuntimeError("PREDICTION_RANKING_INVALID")
        for field in ("entry_bid", "entry_ask", "entry_price"):
            value = row.get(field)
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise RuntimeError("PREDICTION_RANKING_INVALID")
        if (row["entry_bid"] > row["entry_ask"]
                or row["entry_price"] != row["entry_ask"]
                or row.get("entry_price_method") != "SNAPSHOT_BEST_ASK_NOT_FILLED"):
            raise RuntimeError("PREDICTION_RANKING_INVALID")
        identity = (row["symbol"], row["expiry"], strike, row["option_type"])
        if identity in seen:
            raise RuntimeError("PREDICTION_RANKING_INVALID")
        seen.add(identity)
    return True


def validate_quote_exchange_times(quotes, captured_at, *, checked_at):
    """Fail closed if self-reported capture time masks an old exchange quote.

    This verifies internal quote age/identity only; exchange time fields are
    supplied by the broker response and are not independent authentication.
    """
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise RuntimeError("QUOTE_CAPTURE_TIME_INVALID")
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise RuntimeError("QUOTE_PUBLICATION_TIME_INVALID")
    # A publication check must be contemporaneous with (or after) capture.
    if (captured_at - checked_at).total_seconds() > 5:
        raise RuntimeError("QUOTE_PUBLICATION_TIME_INVALID")
    seen_symbols = set()
    seen_tokens = set()
    for row in quotes:
        if not isinstance(row, dict):
            raise RuntimeError("QUOTE_CONTRACT_IDENTITY_MISMATCH")
        contract, quote = row.get("contract"), row.get("quote")
        if not isinstance(contract, dict) or not isinstance(quote, dict):
            raise RuntimeError("QUOTE_CONTRACT_IDENTITY_MISMATCH")
        if (not contract.get("tradingsymbol")
                or not contract.get("symboltoken")
                or quote.get("tradingSymbol") != contract["tradingsymbol"]
                or str(quote.get("symbolToken")) != str(contract["symboltoken"])):
            raise RuntimeError("QUOTE_CONTRACT_IDENTITY_MISMATCH")
        # A token or trading symbol must identify exactly one NFO contract
        # in a capture. Duplicate rows can double-count OI/volume and falsely
        # corroborate a prediction even when each row's quote matches itself.
        symbol = contract["tradingsymbol"]
        token = str(contract["symboltoken"])
        if symbol in seen_symbols or token in seen_tokens:
            raise RuntimeError("QUOTE_CONTRACT_DUPLICATE")
        seen_symbols.add(symbol)
        seen_tokens.add(token)
        feed_time = quote.get("exchFeedTime")
        if not isinstance(feed_time, str) or not feed_time.strip():
            raise RuntimeError("QUOTE_EXCHANGE_TIME_INVALID")
        try:
            exchange_time = datetime.strptime(
                feed_time, "%d-%b-%Y %H:%M:%S"
            ).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        except ValueError:
            try:
                exchange_time = datetime.fromisoformat(feed_time)
            except ValueError as exc:
                raise RuntimeError("QUOTE_EXCHANGE_TIME_INVALID") from exc
            if exchange_time.tzinfo is None or exchange_time.utcoffset() is None:
                raise RuntimeError("QUOTE_EXCHANGE_TIME_INVALID")
        age_seconds = (captured_at - exchange_time).total_seconds()
        if age_seconds < -5:
            raise RuntimeError("QUOTE_EXCHANGE_TIME_FUTURE")
        if age_seconds > 120:
            raise RuntimeError("QUOTE_EXCHANGE_TIME_STALE")
        # A child may spend minutes writing its receipt after capture.
        # A quote must remain fresh at the moment proof is published.
        publication_age_seconds = (checked_at - exchange_time).total_seconds()
        if publication_age_seconds < -5:
            raise RuntimeError("QUOTE_EXCHANGE_TIME_FUTURE")
        if publication_age_seconds > 120:
            raise RuntimeError("QUOTE_EXCHANGE_TIME_STALE")
    return True


def validate_ranking_quote_binding(payload, quotes):
    """Bind each ranked contract to a unique captured read-only quote identity.

    This proves internal identity agreement only; neither a captured quote nor
    its self-reported identity is independent broker authentication.
    """
    quote_identities = set()
    for row in quotes:
        if not isinstance(row, dict) or not isinstance(row.get("contract"), dict):
            continue
        contract = row["contract"]
        symbol, token = contract.get("tradingsymbol"), contract.get("symboltoken")
        if isinstance(symbol, str) and symbol and str(token).isdigit():
            quote_identities.add((symbol, str(token)))
    used = set()
    for rank in payload["ranking"]:
        identity = (rank["tradingsymbol"], rank["symboltoken"])
        if identity not in quote_identities:
            raise RuntimeError("RANK_QUOTE_IDENTITY_MISMATCH")
        if identity in used:
            raise RuntimeError("RANK_QUOTE_DUPLICATE")
        used.add(identity)
    return True



def validate_ranking_contract_terms(payload, quotes):
    """Bind each ranked option to captured underlying, expiry, strike and side.

    Symbol/token and depth agreement alone cannot establish contract terms.
    This is internal consistency only, not independent master authentication.
    """
    by_identity = {
        (row["contract"]["tradingsymbol"], str(row["contract"]["symboltoken"])): row["contract"]
        for row in quotes
    }
    for rank in payload["ranking"]:
        contract = by_identity.get((rank["tradingsymbol"], rank["symboltoken"]))
        if not isinstance(contract, dict):
            raise RuntimeError("RANK_QUOTE_CONTRACT_TERMS_MISMATCH")
        strike = contract.get("strike")
        if (contract.get("underlying") != rank["symbol"]
                or contract.get("expiry") != rank["expiry"]
                or contract.get("option_type") != rank["option_type"]
                or type(strike) not in (int, float)
                or not math.isfinite(strike)
                or strike != rank["strike"]):
            raise RuntimeError("RANK_QUOTE_CONTRACT_TERMS_MISMATCH")
    return True


def validate_ranking_quote_prices(payload, quotes):
    """Match ranked PAPER entry prices to the exact captured best bid/ask.

    This proves internal depth/entry agreement, not broker quote authenticity,
    executable liquidity, or a fill. Never infer a real execution from this.
    """
    quote_by_identity = {
        (row["contract"]["tradingsymbol"], str(row["contract"]["symboltoken"])): row["quote"]
        for row in quotes
    }
    for rank in payload["ranking"]:
        identity = (rank["tradingsymbol"], rank["symboltoken"])
        quote = quote_by_identity.get(identity)
        if not isinstance(quote, dict):
            raise RuntimeError("RANK_QUOTE_IDENTITY_MISMATCH")
        depth = quote.get("depth")
        if not isinstance(depth, dict):
            raise RuntimeError("RANK_QUOTE_DEPTH_INVALID")
        buy, sell = depth.get("buy"), depth.get("sell")
        if not isinstance(buy, list) or not buy or not isinstance(sell, list) or not sell:
            raise RuntimeError("RANK_QUOTE_DEPTH_INVALID")
        try:
            best_bid_raw, best_ask_raw = buy[0]["price"], sell[0]["price"]
            if type(best_bid_raw) is bool or type(best_ask_raw) is bool:
                raise ValueError("Boolean price")
            best_bid, best_ask = float(best_bid_raw), float(best_ask_raw)
        except (TypeError, KeyError, ValueError, OverflowError):
            raise RuntimeError("RANK_QUOTE_DEPTH_INVALID") from None
        if (not math.isfinite(best_bid) or not math.isfinite(best_ask)
                or best_bid <= 0 or best_ask < best_bid):
            raise RuntimeError("RANK_QUOTE_DEPTH_INVALID")
        if rank["entry_bid"] != best_bid or rank["entry_ask"] != best_ask:
            raise RuntimeError("RANK_QUOTE_PRICE_MISMATCH")
    return True


def validate_instrument_master_provenance(raw_snapshot, payload):
    """Bind the captured master digest to the forecast's declared master.

    This establishes internal agreement only, not external master authenticity.
    """
    provenance = payload.get("provenance") if isinstance(payload, dict) else None
    captured_digest = (raw_snapshot.get("instrument_master_sha256")
                       if isinstance(raw_snapshot, dict) else None)
    predicted_digest = (provenance.get("instrument_master_sha256")
                        if isinstance(provenance, dict) else None)
    for digest in (captured_digest, predicted_digest):
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError("INSTRUMENT_MASTER_PROVENANCE_INVALID")
    if captured_digest != predicted_digest:
        raise RuntimeError("INSTRUMENT_MASTER_PROVENANCE_MISMATCH")
    return True




def validate_prediction_lineage(payload, source_hash):
    """Bind run identity to the captured source and declared model version.

    This validates self-reported PAPER provenance, not the underlying model
    computation or external market data authenticity.
    """
    version = payload.get("model_version")
    features_hash = payload.get("features_hash")
    run_id = payload.get("run_id")
    if (not isinstance(version, str) or not version.strip()
            or not isinstance(features_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", features_hash) is None
            or not isinstance(run_id, str)
            or re.fullmatch(r"[0-9a-f]{64}", run_id) is None):
        raise RuntimeError("PREDICTION_LINEAGE_INVALID")
    from phase2.daily_close import canonical_hash
    expected_run_id = canonical_hash({
        "raw_snapshot_sha256": source_hash,
        "model_version": version,
    })
    if run_id != expected_run_id:
        raise RuntimeError("PREDICTION_RUN_ID_MISMATCH")
    return True


def validate_paper_receipt_metadata(receipt):
    """Reject contradictory BigQuery write claims in a local-only PAPER receipt.

    Metadata is self-asserted, not evidence of a BigQuery insertion or query.
    """
    expected_source = "ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT"
    expected_table = "fno-angel-prod-1790444589.PAPER_TRADING_SANDBOX_PHASE2.prediction_ledger"
    if (not isinstance(receipt, dict)
            or receipt.get("status") != "LOCAL_ARTIFACT_ONLY_NOT_INSERTED"
            or receipt.get("source_kind") != expected_source
            or receipt.get("destination_table") != expected_table
            or "bigquery_insert_id" not in receipt
            or receipt["bigquery_insert_id"] is not None
            or "bigquery_job_id" not in receipt
            or receipt["bigquery_job_id"] is not None):
        raise RuntimeError("RECEIPT_METADATA_INVALID")
    return True

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--once", action="store_true")
    args = parser.parse_args()
    # Invalidate any previous success before *any* --once startup guard can fail.
    # Preflight is read-only and must not alter the last run's status.
    if args.once:
        PROOF.mkdir(parents=True, exist_ok=True)
        (PROOF / "status.json").write_text(json.dumps({
            "status": "RUNNING_NOT_VERIFIED", "paper_mode": 1,
            "live_order_authority": 0, "real_broker_orders": 0,
            "broker_order_audit": "NOT_PERFORMED"
        }, sort_keys=True) + "\n", encoding="utf-8")
    validate_environment()
    if args.preflight:
        print(json.dumps(snapshot(), sort_keys=True))
        return 0
    runtime = Path(os.environ.get("CLOUD_PAPER_RUNTIME_DIR", "")).resolve()
    if not runtime.is_dir() or git(runtime, "branch", "--show-current") != "test-framework":
        raise RuntimeError("WRITE_GUARD: separate test-framework checkout required")
    # Prevent the child writer from overriding inherited fail-closed flags via .env.
    if (runtime / ".env").exists():
        raise RuntimeError("UNREVIEWED_ENV_FILE_IN_CHILD_RUNTIME")
    # A tracked or prior-session receipt is never proof that this invocation ran.
    source = runtime / "data" / "paper_ledger" / "receipt.json"
    before_receipt = source.read_bytes() if source.is_file() else None
    started_at = datetime.now(timezone.utc)
    # The writer itself retains all its existing branch, broker and PAPER gates.
    env = dict(os.environ, PAPER_MODE="1", LIVE_ORDER_AUTHORITY="0",
               REAL_BROKER_ORDERS="0", PAPER_LEDGER_BRANCH="test-framework")
    try:
        result = subprocess.run([sys.executable, "run_phase2_local.py"],
                                cwd=runtime, env=env, check=False,
                                timeout=CHILD_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # subprocess.run terminates and waits for the direct child on timeout.
        # No prior successful receipt may survive as current-run evidence.
        (PROOF / "status.json").write_text(json.dumps({
            "status": "FAIL_CLOSED", "error_type": "CHILD_TIMEOUT",
            "child_exit_code": 124, "broker_order_audit": "NOT_PERFORMED"
        }, sort_keys=True) + "\n", encoding="utf-8")
        return 124
    if result.returncode:
        (PROOF / "status.json").write_text(json.dumps({
            "status": "FAIL_CLOSED", "error_type": "CHILD_EXIT_NONZERO",
            "child_exit_code": result.returncode,
            "broker_order_audit": "NOT_PERFORMED"
        }, sort_keys=True) + "\n", encoding="utf-8")
        return result.returncode
    if not source.is_file():
        raise RuntimeError("RECEIPT_MISSING")
    # Read once: the bytes validated below must be the bytes published as proof.
    receipt_bytes = source.read_bytes()
    if before_receipt is not None and receipt_bytes == before_receipt:
        raise RuntimeError("RECEIPT_NOT_REFRESHED")
    receipt = json.loads(receipt_bytes)
    if (not exact_paper_flags(receipt)
            or receipt.get("status") != "LOCAL_ARTIFACT_ONLY_NOT_INSERTED"):
        raise RuntimeError("RECEIPT_SAFETY_FAILURE")
    validate_paper_receipt_metadata(receipt)
    from phase2.daily_close import canonical_hash
    payload = json.loads(receipt["bigquery_merge_parameters"]["payload"])
    # A valid hash is not authorization: the prediction itself must be PAPER.
    # Do not coerce booleans, strings, or a contradictory optional order flag.
    if (not isinstance(payload, dict)
            or payload.get("mode") != "PAPER"
            or type(payload.get("live_order_authority")) is not int
            or payload["live_order_authority"] != 0
            or ("real_broker_orders" in payload
                and (type(payload["real_broker_orders"]) is not int
                     or payload["real_broker_orders"] != 0))):
        raise RuntimeError("PREDICTION_SAFETY_FAILURE")
    validate_prediction_ranking(payload)
    try:
        issued_at = datetime.fromisoformat(payload["created_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("RECEIPT_TIMESTAMP_INVALID") from exc
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise RuntimeError("RECEIPT_TIMESTAMP_INVALID")
    if not (started_at <= issued_at.astimezone(timezone.utc)
            <= datetime.now(timezone.utc) + timedelta(seconds=5)):
        raise RuntimeError("RECEIPT_NOT_FROM_CURRENT_RUN")
    # All three artifacts must refer to the same broker snapshot provenance.
    # This is consistency validation, not proof that the snapshot was live.
    source_hash = payload.get("source_hash")
    if (not isinstance(source_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None
            or receipt.get("source_hash") != source_hash):
        raise RuntimeError("SOURCE_PROVENANCE_MISMATCH")
    validate_prediction_lineage(payload, source_hash)
    # Bind the signed-off prediction hash to the actual captured broker snapshot
    # bytes. Internal agreement among receipt/entry/DNA alone is insufficient.
    raw = runtime / "data" / "raw_snapshot.json"
    if not raw.is_file():
        raise RuntimeError("RAW_SNAPSHOT_MISSING")
    raw_bytes = raw.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != source_hash:
        raise RuntimeError("RAW_SNAPSHOT_HASH_MISMATCH")
    try:
        raw_snapshot = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("RAW_SNAPSHOT_INVALID") from exc
    if (not isinstance(raw_snapshot, dict)
            or raw_snapshot.get("captured_at") != payload.get("source_timestamp")):
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_MISMATCH")
    # Hash equality and timestamp equality alone can certify a replayed snapshot.
    # The Phase 2 child captures its broker snapshot after this invocation starts.
    try:
        source_captured_at = datetime.fromisoformat(raw_snapshot["captured_at"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_INVALID") from exc
    if source_captured_at.tzinfo is None or source_captured_at.utcoffset() is None:
        raise RuntimeError("RAW_SNAPSHOT_TIMESTAMP_INVALID")
    if not (started_at <= source_captured_at.astimezone(timezone.utc)
            <= datetime.now(timezone.utc) + timedelta(seconds=5)):
        raise RuntimeError("RAW_SNAPSHOT_NOT_FROM_CURRENT_RUN")
    # A forward-issued PAPER forecast cannot predate the market snapshot
    # it claims as its input, even when both times satisfy freshness gates.
    # Compare absolute instants so differing timezone offsets cannot mask
    # a reversed causal order. The reviewed Phase 2 writer uses equality.
    if issued_at.astimezone(timezone.utc) < source_captured_at.astimezone(timezone.utc):
        raise RuntimeError("PREDICTION_PRECEDES_SOURCE_CAPTURE")
    # The raw capture must declare the reviewed read-only source and agree
    # with the forecast provenance. These fields are self-asserted, NOT
    # independent proof of broker authentication or tick freshness.
    expected_source_kind = "ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT"
    if raw_snapshot.get("source_kind") != expected_source_kind:
        raise RuntimeError("SOURCE_KIND_NOT_BROKER_READONLY")
    provenance = payload.get("provenance")
    if (not isinstance(provenance, dict)
            or provenance.get("source_kind") != expected_source_kind):
        raise RuntimeError("SOURCE_KIND_PROVENANCE_MISMATCH")
    validate_instrument_master_provenance(raw_snapshot, payload)
    quotes = raw_snapshot.get("quotes")
    if not isinstance(quotes, list) or not quotes:
        raise RuntimeError("RAW_SNAPSHOT_QUOTES_MISSING")
    validate_quote_exchange_times(quotes, source_captured_at, checked_at=datetime.now(timezone.utc))
    validate_ranking_quote_binding(payload, quotes)
    validate_ranking_contract_terms(payload, quotes)
    validate_ranking_quote_prices(payload, quotes)
    digest = canonical_hash({k: v for k, v in payload.items() if k != "prediction_hash"})
    if not (digest == receipt["prediction_hash"] == payload["prediction_hash"]
            == receipt["bigquery_merge_parameters"]["hash"]):
        raise RuntimeError("RECEIPT_HASH_FAILURE")
    entry = runtime / "data" / "paper_ledger" / ("entry_" + digest + ".json")
    dna = runtime / "data" / "anomaly_logs" / ("dna_" + digest + ".json")
    if not entry.is_file() or not dna.is_file():
        raise RuntimeError("LINKED_EVIDENCE_MISSING")
    linked_evidence_bytes = {}
    for path in (entry, dna):
        evidence_bytes = path.read_bytes()
        data = json.loads(evidence_bytes)
        if (data.get("prediction_hash") != digest
                or data.get("source_hash") != source_hash
                or not exact_paper_flags(data)):
            raise RuntimeError("LINKED_EVIDENCE_INVALID")
        linked_evidence_bytes[path.name] = evidence_bytes
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / source.name).write_bytes(receipt_bytes)
    for filename, evidence_bytes in linked_evidence_bytes.items():
        (PROOF / filename).write_bytes(evidence_bytes)
    # Preserve the verified bytes rather than re-reading a mutable source file.
    (PROOF / "raw_snapshot.json").write_bytes(raw_bytes)
    # Recheck immediately before publishing success: hashing/copying may take
    # time after the initial check, especially on degraded cloud storage.
    publish_checked_at = datetime.now(timezone.utc)
    validate_quote_exchange_times(quotes, source_captured_at, checked_at=publish_checked_at)
    (PROOF / "status.json").write_text(json.dumps({
        "status": "PAPER_RECEIPT_VERIFIED",
        "quote_freshness_checked_at": publish_checked_at.isoformat(),
        "prediction_hash": digest,
        "runtime_sha": git(runtime, "rev-parse", "HEAD"),
        "paper_mode": 1,
        "live_order_authority": 0,
        "real_broker_orders": 0,
        "broker_order_audit": "NOT_PERFORMED"
    }, sort_keys=True) + "\n", encoding="utf-8")
    print("PAPER_RECEIPT_VERIFIED")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # A read-only --preflight must never overwrite a previous PAPER run's
        # evidence, even when its environment validation fails. Only a valid
        # --once invocation owns the run-status lifecycle.
        if sys.argv[1:] == ["--once"]:
            PROOF.mkdir(parents=True, exist_ok=True)
            (PROOF / "status.json").write_text(json.dumps({
                "status": "FAIL_CLOSED",
                "error_type": type(exc).__name__,
                "missing_snapshot_variable_names": [
                    name for name in REQUIRED[:4] if not os.getenv(name)
                ],
                "paper_mode": os.getenv("PAPER_MODE") == "1",
                "live_order_authority": os.getenv("LIVE_ORDER_AUTHORITY") == "0",
                "real_broker_orders": os.getenv("REAL_BROKER_ORDERS") == "0",
            }, sort_keys=True) + "\n", encoding="utf-8")
        print("CLOUD_PAPER_RUNNER_FAIL_CLOSED type=" + type(exc).__name__,
              file=sys.stderr)
        sys.exit(1)
