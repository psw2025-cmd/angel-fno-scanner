"""
tests/test_colab_contract.py

Comprehensive tests for Section 13: COLAB DATA CONTRACT.
Verifies:
1. Canonical alias dictionary explicitly maps:
   - Fut LTP -> FUTURES_LTP
   - Fut Chg % -> FUTURES_CHANGE_PCT
   - CE LTP -> CE_LTP
   - CE Chg % -> CE_CHANGE_PCT
   - CE OI -> CE_OI
   - PE LTP -> PE_LTP
   - PE Chg % -> PE_CHANGE_PCT
   - PE OI -> PE_OI
   - ATM PCR -> PCR
2. Zero fuzzy/first-match semantic guessing (exact mapping only).
3. Missing or ambiguous required fields strictly raise SCHEMA_FAIL.
"""

import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import pytest

CONTRACT_PATH = Path(r"C:\AngelFNO_Workstation\reports\final_e2e_truth_20261001_114500\17_COLAB_SCHEMA_CONTRACT.json")

# Explicit canonical alias mapping contract
EXPLICIT_ALIAS_MAP = {
    "Fut LTP": "FUTURES_LTP",
    "Fut Chg %": "FUTURES_CHANGE_PCT",
    "CE LTP": "CE_LTP",
    "CE Chg %": "CE_CHANGE_PCT",
    "CE OI": "CE_OI",
    "PE LTP": "PE_LTP",
    "PE Chg %": "PE_CHANGE_PCT",
    "PE OI": "PE_OI",
    "ATM PCR": "PCR",
    "ATM Strike": "ATM_STRIKE",
    "ATM CE Contract": "ATM_CE_CONTRACT",
    "ATM PE Contract": "ATM_PE_CONTRACT",
    "Forensic Action Signal": "ACTION_SIGNAL",
    "Timestamp (IST)": "TIMESTAMP_IST"
}

REQUIRED_DASHBOARD_FIELDS = {
    "FUTURES_LTP",
    "FUTURES_CHANGE_PCT",
    "CE_LTP",
    "CE_CHANGE_PCT",
    "CE_OI",
    "PE_LTP",
    "PE_CHANGE_PCT",
    "PE_OI",
    "PCR"
}


class SchemaFail(Exception):
    """Raised when required schema fields are missing or ambiguous."""
    pass


def map_raw_headers_to_canonical(headers: list[str]) -> dict[str, str]:
    """
    Transforms raw Google Sheet column headers to canonical internal names.
    Enforces exact dictionary lookup; strictly prohibits fuzzy / first-match heuristics.
    """
    mapped = {}
    seen_canonical = set()

    for h in headers:
        clean_h = str(h).strip()
        if clean_h in EXPLICIT_ALIAS_MAP:
            canonical = EXPLICIT_ALIAS_MAP[clean_h]
            if canonical in seen_canonical:
                raise SchemaFail(f"SCHEMA_FAIL: Ambiguous duplicate canonical field detected: '{canonical}'")
            mapped[clean_h] = canonical
            seen_canonical.add(canonical)

    # Check for missing required fields
    missing = REQUIRED_DASHBOARD_FIELDS - seen_canonical
    if missing:
        raise SchemaFail(f"SCHEMA_FAIL: Required fields missing from upstream payload: {sorted(list(missing))}")

    return mapped


def resolve_colab_contract_path(candidates: list[Path]) -> Path:
    """Never certify an unavailable external contract as a skipped success.

    This only locates the real artifact; it does not generate or replace one.
    """
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "COLAB_SCHEMA_CONTRACT_BLOCKED: authentic 17_COLAB_SCHEMA_CONTRACT.json "
        "is unavailable; external schema certification cannot pass"
    )


def verify_colab_contract_digest(path: Path, expected_sha256: str | None) -> bytes:
    """Bind loaded bytes to an independently recorded expected digest.

    A matching digest proves byte integrity only; the expected digest must
    still be established from an authentic, independently reviewed source.
    """
    if not expected_sha256 or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError(
            "COLAB_SCHEMA_DIGEST_BLOCKED: independently verified SHA-256 "
            "digest is required before external-contract certification"
        )
    payload = path.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual, expected_sha256.lower()):
        raise ValueError("COLAB_SCHEMA_DIGEST_MISMATCH: external contract bytes differ")
    return payload


def test_colab_digest_requires_expected_hash(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="COLAB_SCHEMA_DIGEST_BLOCKED"):
        verify_colab_contract_digest(fixture, None)
    with pytest.raises(ValueError, match="COLAB_SCHEMA_DIGEST_BLOCKED"):
        verify_colab_contract_digest(fixture, "invalid")


def test_colab_digest_rejects_mismatch(tmp_path):
    fixture = tmp_path / "fixture.json"
    fixture.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="COLAB_SCHEMA_DIGEST_MISMATCH"):
        verify_colab_contract_digest(fixture, "0" * 64)


def test_colab_digest_accepts_matching_fixture_only(tmp_path):
    """Synthetic fixture tests hashing, NOT provenance or schema authenticity."""
    fixture = tmp_path / "fixture.json"
    payload = b'{"canonical_column_aliases": {}}'
    fixture.write_bytes(payload)
    assert verify_colab_contract_digest(fixture, hashlib.sha256(payload).hexdigest()) == payload


def test_missing_colab_contract_is_hard_failure(tmp_path):
    """Negative regression: absent external evidence must not be a pytest skip."""
    with pytest.raises(FileNotFoundError, match="COLAB_SCHEMA_CONTRACT_BLOCKED"):
        resolve_colab_contract_path([tmp_path / "17_COLAB_SCHEMA_CONTRACT.json"])


def test_colab_contract_resolver_uses_existing_file(tmp_path):
    """Resolver-only fixture; not evidence of an authentic Colab contract."""
    candidate = tmp_path / "17_COLAB_SCHEMA_CONTRACT.json"
    candidate.write_text("{}", encoding="utf-8")
    assert resolve_colab_contract_path([tmp_path / "absent.json", candidate]) == candidate


def test_colab_contract_json_matches_specification():
    configured = os.environ.get("COLAB_SCHEMA_CONTRACT_PATH")
    # Explicit override must not silently fall back to a stale local copy.
    candidates = [Path(configured)] if configured else [
        CONTRACT_PATH,
        Path("/mnt/c/AngelFNO_Workstation/reports/final_e2e_truth_20261001_114500/17_COLAB_SCHEMA_CONTRACT.json"),
    ]
    path = resolve_colab_contract_path(candidates)
    # An arbitrary local JSON file cannot satisfy this gate without a pinned
    # digest. Digest matching is necessary, not sufficient, for provenance.
    raw = verify_colab_contract_digest(path, os.environ.get("COLAB_SCHEMA_CONTRACT_SHA256"))
    contract = json.loads(raw.decode("utf-8"))
    
    aliases = contract["canonical_column_aliases"]
    assert aliases["Fut LTP"] == "FUTURES_LTP"
    assert aliases["Fut Chg %"] == "FUTURES_CHANGE_PCT"
    assert aliases["CE LTP"] == "CE_LTP"
    assert aliases["CE Chg %"] == "CE_CHANGE_PCT"
    assert aliases["CE OI"] == "CE_OI"
    assert aliases["PE LTP"] == "PE_LTP"
    assert aliases["PE Chg %"] == "PE_CHANGE_PCT"
    assert aliases["PE OI"] == "PE_OI"
    assert aliases["ATM PCR"] == "PCR"


def test_valid_forensic_live_headers_map_successfully():
    forensic_headers = [
        "Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %", "Fut OBI",
        "ATM Strike", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI", "CE OBI",
        "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR", "Forensic Action Signal"
    ]
    mapped = map_raw_headers_to_canonical(forensic_headers)
    assert mapped["Fut LTP"] == "FUTURES_LTP"
    assert mapped["Fut Chg %"] == "FUTURES_CHANGE_PCT"
    assert mapped["CE LTP"] == "CE_LTP"
    assert mapped["CE Chg %"] == "CE_CHANGE_PCT"
    assert mapped["CE OI"] == "CE_OI"
    assert mapped["PE LTP"] == "PE_LTP"
    assert mapped["PE Chg %"] == "PE_CHANGE_PCT"
    assert mapped["PE OI"] == "PE_OI"
    assert mapped["ATM PCR"] == "PCR"


def test_missing_required_field_raises_schema_fail():
    incomplete_headers = [
        "Symbol", "Fut LTP", "CE LTP", "PE LTP"  # Missing PCR, OI, Chg %
    ]
    with pytest.raises(SchemaFail) as exc_info:
        _ = map_raw_headers_to_canonical(incomplete_headers)
    assert "SCHEMA_FAIL: Required fields missing" in str(exc_info.value)
    assert "PCR" in str(exc_info.value)


def test_ambiguous_duplicate_header_raises_schema_fail():
    duplicate_headers = [
        "Timestamp (IST)", "Symbol", "Nearest Expiry", "Fut LTP", "Fut Chg %",
        "ATM Strike", "ATM CE Contract", "CE LTP", "CE Chg %", "CE OI",
        "ATM PE Contract", "PE LTP", "PE Chg %", "PE OI", "ATM PCR",
        "Fut LTP"  # Duplicate column
    ]
    with pytest.raises(SchemaFail) as exc_info:
        _ = map_raw_headers_to_canonical(duplicate_headers)
    assert "SCHEMA_FAIL: Ambiguous duplicate" in str(exc_info.value)


def test_no_generic_fuzzy_first_match():
    # Attempting to use a fuzzy or generic name like "LTP" or "Change" without exact prefix
    fuzzy_headers = [
        "LTP", "Price", "Change", "Volume", "OI"
    ]
    with pytest.raises(SchemaFail) as exc_info:
        _ = map_raw_headers_to_canonical(fuzzy_headers)
    assert "SCHEMA_FAIL: Required fields missing" in str(exc_info.value)
