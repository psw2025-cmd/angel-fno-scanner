"""Credential presence and PAPER-only lifecycle checks; never log secrets."""
import os
from contextlib import contextmanager

REQUIRED = (
    "ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN",
    "ANGEL_TOTP_SEED", "ANGEL_EXCHANGE_TYPE", "ANGEL_SYMBOL_TOKEN",
)

def enforce_safety():
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY") != "0":
        raise RuntimeError("PAPER-only authority flags required")

def validate_environment(*, streaming=False):
    enforce_safety()
    required = REQUIRED if streaming else REQUIRED[:4]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError("Missing required variable names: " + ", ".join(missing))
    if not streaming:
        return True
    try:
        exchange = int(os.environ["ANGEL_EXCHANGE_TYPE"])
    except ValueError as exc:
        raise RuntimeError("ANGEL_EXCHANGE_TYPE must be an integer") from exc
    if exchange not in (1, 2, 3, 4, 5, 6, 7):
        raise RuntimeError("Unsupported exchange type")
    if not os.environ["ANGEL_SYMBOL_TOKEN"].isdigit():
        raise RuntimeError("ANGEL_SYMBOL_TOKEN must be numeric")
    return True

@contextmanager
def broker_session(provider_factory):
    """Use existing Phase 2 provider; best-effort logout without leaking exception text."""
    validate_environment()
    provider = None
    try:
        provider = provider_factory()
        yield provider
    finally:
        client = getattr(provider, "client", None) if provider is not None else None
        logout = getattr(client, "terminateSession", None)
        if callable(logout):
            try:
                logout(os.environ["ANGEL_CLIENT_CODE"])
            except Exception:
                # Cleanup errors must never print SDK responses or credentials.
                pass
