"""Read-only provider adapter for an explicitly configured authorized JSON chain endpoint."""
import os
from datetime import datetime, timezone
import requests
from phase2.option_stream import RateLimited, enforce_paper_mode

class AuthorizedChainProvider:
    def __init__(self, *, endpoint=None, token=None, session=None):
        enforce_paper_mode()
        self.endpoint = endpoint or os.environ["PHASE2_CHAIN_ENDPOINT"]
        self.token = token or os.environ["PHASE2_MARKETDATA_TOKEN"]
        if not self.endpoint.startswith("https://"):
            raise ValueError("HTTPS provider endpoint required")
        self.session = session or requests.Session()

    def fetch_chain(self, symbol):
        enforce_paper_mode()
        if symbol not in ("NIFTY", "BANKNIFTY"):
            raise ValueError("Unsupported underlying")
        response = self.session.get(self.endpoint, params={"symbol": symbol}, headers={"Authorization": "Bearer " + self.token}, timeout=(5, 15))
        if response.status_code == 429:
            retry = response.headers.get("Retry-After")
            raise RateLimited(float(retry) if retry and retry.isdigit() else None)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("symbol") != symbol:
            raise ValueError("Provider payload identity mismatch")
        return data
