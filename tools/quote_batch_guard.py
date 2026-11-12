"""Fail-closed integrity validation for one read-only Angel FULL quote batch.

This module never calls a broker, writes market data, or places orders.
"""


class QuoteBatchIntegrityError(RuntimeError):
    """A quote response cannot prove complete identity coverage."""

    def __init__(self, code):
        self.code = code
        super().__init__(f"BROKER_QUOTE_{code}")


def require_complete_quote_chunk(requested_tokens, response):
    """Return quotes only if every requested identity appears exactly once.

    Partial, duplicate, unexpected, or malformed broker responses are rejected.
    Token values and response contents are intentionally absent from errors.
    """
    requested = [str(token).strip() for token in requested_tokens]
    if not requested or any(token in ("", "None") for token in requested):
        raise QuoteBatchIntegrityError("INVALID_REQUEST")
    if len(set(requested)) != len(requested):
        raise QuoteBatchIntegrityError("DUPLICATE_REQUEST")
    if not isinstance(response, dict) or response.get("status") is not True:
        raise QuoteBatchIntegrityError("BAD_STATUS")
    data = response.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("fetched"), list):
        raise QuoteBatchIntegrityError("MALFORMED_RESPONSE")
    if data.get("unfetched") not in (None, [], {}):
        raise QuoteBatchIntegrityError("UNFETCHED_PRESENT")

    expected = set(requested)
    quotes = {}
    for item in data["fetched"]:
        if not isinstance(item, dict):
            raise QuoteBatchIntegrityError("MALFORMED_QUOTE")
        raw_token = item.get("symbolToken")
        if raw_token is None or isinstance(raw_token, bool):
            raise QuoteBatchIntegrityError("MISSING_TOKEN")
        token = str(raw_token).strip()
        if not token:
            raise QuoteBatchIntegrityError("MISSING_TOKEN")
        if token not in expected:
            raise QuoteBatchIntegrityError("UNEXPECTED_TOKEN")
        if token in quotes:
            raise QuoteBatchIntegrityError("DUPLICATE_TOKEN")
        quotes[token] = item
    if len(quotes) != len(requested):
        raise QuoteBatchIntegrityError("MISSING_TOKEN")
    return quotes
