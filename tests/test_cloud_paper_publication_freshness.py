"""Offline regression: a fresh capture can be stale by final PAPER publication.

No broker access, credentials, network, or real orders.
"""
import inspect
import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from cloud_runner import main as runner

IST = ZoneInfo("Asia/Kolkata")
CAPTURE = datetime(2026, 10, 23, 9, 15, 30, tzinfo=IST)


def row(exchange_time="23-Oct-2026 09:15:20"):
    return {
        "contract": {"tradingsymbol": "TEST26OCT100CE", "symboltoken": "123"},
        "quote": {"tradingSymbol": "TEST26OCT100CE", "symbolToken": "123",
                  "exchFeedTime": exchange_time},
    }


class PublicationFreshnessTests(unittest.TestCase):
    def test_quote_fresh_at_publication_is_accepted(self):
        self.assertTrue(runner.validate_quote_exchange_times(
            [row()], CAPTURE, checked_at=CAPTURE + timedelta(seconds=20)))

    def test_quote_fresh_at_capture_but_stale_after_child_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "QUOTE_EXCHANGE_TIME_STALE"):
            runner.validate_quote_exchange_times(
                [row()], CAPTURE, checked_at=CAPTURE + timedelta(minutes=10))

    def test_quote_near_capture_age_limit_cannot_age_past_limit(self):
        with self.assertRaisesRegex(RuntimeError, "QUOTE_EXCHANGE_TIME_STALE"):
            runner.validate_quote_exchange_times(
                [row("23-Oct-2026 09:13:40")], CAPTURE,
                checked_at=CAPTURE + timedelta(seconds=20))

    def test_publication_time_must_be_aware(self):
        with self.assertRaisesRegex(RuntimeError, "QUOTE_PUBLICATION_TIME_INVALID"):
            runner.validate_quote_exchange_times(
                [row()], CAPTURE, checked_at=datetime(2026, 10, 23, 9, 16))

    def test_main_passes_current_time_before_verified_status(self):
        source = inspect.getsource(runner.main)
        gate = "validate_quote_exchange_times(quotes, source_captured_at, checked_at=datetime.now(timezone.utc))"
        self.assertIn(gate, source)
        self.assertLess(source.index(gate),
                        source.index('"status": "PAPER_RECEIPT_VERIFIED"'))


if __name__ == "__main__":
    unittest.main()
