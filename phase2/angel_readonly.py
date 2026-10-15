"""Read-only Angel One SmartAPI market-data session. No order APIs imported or invoked."""
import os
import pyotp
from SmartApi import SmartConnect
from phase2.option_stream import enforce_paper_mode

class AngelReadOnlyProvider:
    def __init__(self):
        enforce_paper_mode()
        required = ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN", "ANGEL_TOTP_SEED")
        missing = [k for k in required if not os.getenv(k)]
        if missing:
            raise RuntimeError("Missing broker secret names: " + ", ".join(missing))
        self.client = SmartConnect(api_key=os.environ["ANGEL_API_KEY"])
        response = self.client.generateSession(os.environ["ANGEL_CLIENT_CODE"], os.environ["ANGEL_PIN"], pyotp.TOTP(os.environ["ANGEL_TOTP_SEED"]).now())
        if not isinstance(response, dict) or response.get("status") is not True or not response.get("data", {}).get("jwtToken"):
            raise RuntimeError("Broker authentication unsuccessful")
    def quote(self, exchange, tradingsymbol, symboltoken):
        enforce_paper_mode()
        if exchange not in ("NSE", "NFO") or not symboltoken or not tradingsymbol:
            raise ValueError("Invalid read-only quote identity")
        result = self.client.getMarketData("FULL", {exchange: [str(symboltoken)]})
        if not isinstance(result, dict) or result.get("status") is not True:
            raise RuntimeError("Broker quote failed")
        rows = result.get("data", {}).get("fetched", [])
        if len(rows) != 1 or str(rows[0].get("symbolToken")) != str(symboltoken):
            raise RuntimeError("Broker quote token mismatch")
        return rows[0]
