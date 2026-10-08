#!/usr/bin/env python3
"""
Unified Credentials & Environment Resolution for Angel F&O Scanner.
Supports both GitHub Actions (environment/secrets) and local workstation (.env / file paths).
"""
import json
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

DEFAULT_KEY_PATHS = [
    Path(r"C:\AngelFNO_Workstation\secrets\gcp-service-account.json"),
    Path("/mnt/c/AngelFNO_Workstation/secrets/gcp-service-account.json"),
    Path.home() / "angel_sheets_key.json",
]


def load_env(env_path=None):
    """
    Lightweight, dependency-free .env loader.
    Populates os.environ without overwriting existing environment variables.
    """
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    else:
        candidates.extend([
            REPO_ROOT / ".env",
            Path(r"C:\AngelFNO_Workstation\.env"),
            Path(r"C:\AngelFNO_Workstation\secrets\.env"),
            Path("/mnt/c/AngelFNO_Workstation/.env"),
            Path("/mnt/c/AngelFNO_Workstation/secrets/.env"),
        ])

    loaded = {}
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                with open(candidate, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
                                v = v[1:-1]
                            if k and k not in os.environ:
                                os.environ[k] = v
                                loaded[k] = v
            except Exception:
                pass
            break
    return loaded


def get_canonical_sheet_id():
    """Return the single authoritative Google Sheet ID declared in agent_manifest.json."""
    manifest_path = REPO_ROOT / "agent_manifest.json"
    if not manifest_path.exists():
        raise RuntimeError("agent_manifest.json is required to resolve the authoritative Google Sheet.")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Cannot read authoritative agent_manifest.json: {exc}") from exc
    canonical = str(
        manifest.get("cloud_resources", {}).get("google_sheet_id", "")
    ).strip()
    if not canonical:
        raise RuntimeError("agent_manifest.json does not define cloud_resources.google_sheet_id.")
    return canonical


def require_authoritative_sheet_id(configured_id=None):
    """
    Fail closed when runtime configuration points at a Sheet other than the
    repository's canonical production Sheet. Returns the canonical ID on success.
    """
    configured = str(configured_id or os.getenv("SHEET_ID", "")).strip()
    canonical = get_canonical_sheet_id()
    if not configured:
        raise RuntimeError("SHEET_ID is required and must match agent_manifest.json.")
    if configured != canonical:
        raise RuntimeError(
            "SHEET_ID authority mismatch: runtime configuration does not match "
            "agent_manifest.json. Refusing to read or write a non-authoritative Sheet."
        )
    return canonical


def resolve_service_account_info(custom_key_path=None):
    """
    Load service-account JSON dictionary from:
    1. SHEETS_KEY_JSON (raw JSON string or file path)
    2. GOOGLE_APPLICATION_CREDENTIALS (file path)
    3. custom_key_path (e.g. KEY_PATH from angel_prediction_engine)
    4. Default workstation key paths
    """
    raw_secret = os.getenv("SHEETS_KEY_JSON", "").strip()
    if raw_secret:
        # Check if raw_secret is an existing file path
        if os.path.exists(raw_secret) and os.path.isfile(raw_secret):
            try:
                with open(raw_secret, "r", encoding="utf-8") as fh:
                    info = json.load(fh)
                if isinstance(info, dict) and info.get("type") == "service_account":
                    return info
            except Exception:
                pass

        # Try parsing as JSON string (handling escaped quotes)
        candidates = [raw_secret]
        normalized = re.sub(r'\\+"', '"', raw_secret)
        if normalized not in candidates:
            candidates.append(normalized)
        if len(raw_secret) >= 2 and raw_secret[0] == raw_secret[-1] and raw_secret[0] in ("'", '"'):
            candidates.append(raw_secret[1:-1])

        for cand in candidates:
            try:
                info = json.loads(cand)
                if isinstance(info, str):
                    info = json.loads(info)
                if isinstance(info, dict) and info.get("type") == "service_account":
                    return info
            except Exception:
                continue

    # Next check GOOGLE_APPLICATION_CREDENTIALS
    gac_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if gac_path and os.path.exists(gac_path) and os.path.isfile(gac_path):
        try:
            with open(gac_path, "r", encoding="utf-8") as fh:
                info = json.load(fh)
            if isinstance(info, dict) and info.get("type") == "service_account":
                return info
        except Exception:
            pass

    # Next check custom_key_path if provided
    if custom_key_path and os.path.exists(custom_key_path) and os.path.isfile(custom_key_path):
        try:
            with open(custom_key_path, "r", encoding="utf-8") as fh:
                info = json.load(fh)
            if isinstance(info, dict) and info.get("type") == "service_account":
                return info
        except Exception:
            pass

    # Next check default paths
    for p in DEFAULT_KEY_PATHS:
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    info = json.load(fh)
                if isinstance(info, dict) and info.get("type") == "service_account":
                    return info
            except Exception:
                pass

    return None


def load_service_account(custom_key_path=None):
    """Return service-account dict or raise informative RuntimeError."""
    info = resolve_service_account_info(custom_key_path=custom_key_path)
    if info:
        return info
    raise RuntimeError(
        "Google Sheets service account credentials not found. "
        "Set SHEETS_KEY_JSON (JSON string or file path), "
        "set GOOGLE_APPLICATION_CREDENTIALS, or place key at "
        r"C:\AngelFNO_Workstation\secrets\gcp-service-account.json."
    )


def get_angel_credentials():
    """Return dictionary of Angel broker credential environment variables."""
    return {
        "ANGEL_API_KEY": os.getenv("ANGEL_API_KEY", "").strip(),
        "ANGEL_CLIENT_CODE": os.getenv("ANGEL_CLIENT_CODE", "").strip(),
        "ANGEL_PIN": os.getenv("ANGEL_PIN", "").strip(),
        "ANGEL_TOTP_SEED": os.getenv("ANGEL_TOTP_SEED", "").strip(),
    }


def validate_angel_credentials():
    """Return list of missing Angel credential names."""
    creds = get_angel_credentials()
    return [name for name, val in creds.items() if not val]
