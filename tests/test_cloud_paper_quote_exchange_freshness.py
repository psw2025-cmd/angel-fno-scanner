"""Offline regression: capture time is not exchange quote freshness.

Tests never authenticate to a broker, access a market, or place orders.
"""
import inspect
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from cloud_runner import main as runner

IST = ZoneInfo("Asia/Kolkata")
CAPTURE = datetime(2026, 10, 23, 9, 15, 30, tzinfo=IST)


def row(feed_time="23-Oct-2026 09:15:15", *, symbol="TEST26OCT100CE", token="123"):
    return {"contract": {"tradingsymbol": symbol, "symboltoken": token},
            "quote": {"tradingSymbol": symbol, "symbolToken": token,
                      "exchFeedTime": feed_time}}


class ExchangeQuoteFreshnessTests(unittest.TestCase):
    def test_current_exchange_time_and_identity_accepted(self):
        self.assertTrue(runner.validate_quote_exchange_times([row()], CAPTURE, checked_at=CAPTURE))

    def test_stale_quote_rejected_even_when_snapshot_capture_is_current(self):
        with self.assertRaisesRegex(RuntimeError, "QUOTE_EXCHANGE_TIME_STALE"):
            runner.validate_quote_exchange_times(
                [row("23-Oct-2026 09:10:00")], CAPTURE, checked_at=CAPTURE)

    def test_future_quote_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "QUOTE_EXCHANGE_TIME_FUTURE"):
            runner.validate_quote_exchange_times(
                [row("23-Oct-2026 09:18:00")], CAPTURE, checked_at=CAPTURE)

    def test_missing_invalid_or_naive_iso_timestamp_rejected(self):
        for value in (None, "", "not-a-time", "2026-10-23T09:15:15"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "QUOTE_EXCHANGE_TIME_INVALID"):
                    runner.validate_quote_exchange_times([row(value)], CAPTURE, checked_at=CAPTURE)

    def test_quote_contract_identity_mismatch_rejected(self):
        for field in ("tradingSymbol", "symbolToken"):
            with self.subTest(field=field):
                altered = row()
                altered["quote"][field] = "DIFFERENT"
                with self.assertRaisesRegex(RuntimeError, "QUOTE_CONTRACT_IDENTITY_MISMATCH"):
                    runner.validate_quote_exchange_times([altered], CAPTURE, checked_at=CAPTURE)

    def test_timezone_aware_iso_supported(self):
        self.assertTrue(runner.validate_quote_exchange_times(
            [row("2026-10-23T03:45:15+00:00")], CAPTURE, checked_at=CAPTURE))

    def test_freshness_gate_runs_before_publishing_verified_status(self):
        source = inspect.getsource(runner.main)
        self.assertIn("validate_quote_exchange_times(quotes, source_captured_at, checked_at=datetime.now(timezone.utc))", source)
        self.assertLess(source.index("validate_quote_exchange_times(quotes, source_captured_at, checked_at=datetime.now(timezone.utc))"),
                        source.index('"status": "PAPER_RECEIPT_VERIFIED"'))


if __name__ == "__main__":
    unittest.main()
