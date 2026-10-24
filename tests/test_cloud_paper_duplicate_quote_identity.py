"""Offline fail-closed contract for duplicate broker option identities.

Synthetic quotes only; no broker, network, cloud, database or order operations.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from cloud_runner import main as runner
from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests, make_receipt


def quotes_for(*pairs):
    stamp = datetime.now(timezone.utc)
    feed = stamp.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d-%b-%Y %H:%M:%S")
    return stamp, [
        {
            "contract": {"tradingsymbol": symbol, "symboltoken": token},
            "quote": {"tradingSymbol": symbol, "symbolToken": token, "exchFeedTime": feed},
        }
        for symbol, token in pairs
    ]


class DuplicateQuoteIdentityTests(unittest.TestCase):
    def test_distinct_quote_identities_pass(self):
        stamp, quotes = quotes_for(("NFO_CE_TEST", "101"), ("NFO_PE_TEST", "102"))
        self.assertTrue(runner.validate_quote_exchange_times(
            quotes, stamp, checked_at=datetime.now(timezone.utc)))

    def test_duplicate_exact_contract_rejected(self):
        stamp, quotes = quotes_for(("NFO_CE_TEST", "101"), ("NFO_CE_TEST", "101"))
        with self.assertRaisesRegex(RuntimeError, "QUOTE_CONTRACT_DUPLICATE"):
            runner.validate_quote_exchange_times(
                quotes, stamp, checked_at=datetime.now(timezone.utc))

    def test_duplicate_token_or_symbol_rejected(self):
        for pairs in (
            (("NFO_CE_TEST", "101"), ("NFO_PE_TEST", "101")),
            (("NFO_CE_TEST", "101"), ("NFO_CE_TEST", "102")),
        ):
            with self.subTest(pairs=pairs):
                stamp, quotes = quotes_for(*pairs)
                with self.assertRaisesRegex(RuntimeError, "QUOTE_CONTRACT_DUPLICATE"):
                    runner.validate_quote_exchange_times(
                        quotes, stamp, checked_at=datetime.now(timezone.utc))

    def test_full_runner_duplicate_quote_cannot_publish_success(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime"
            proof = Path(temp) / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                stamp, quotes = quotes_for(("NFO_CE_TEST", "101"), ("NFO_CE_TEST", "101"))
                make_receipt(runtime, stamp.isoformat(), quotes=quotes)
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "QUOTE_CONTRACT_DUPLICATE"):
                CurrentRunReceiptTests().run_once(runtime, proof, child)
            status = json.loads((proof / "status.json").read_text(encoding="utf-8"))
            self.assertNotEqual(status["status"], "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
