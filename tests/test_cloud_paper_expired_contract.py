"""Offline regression: expired option contracts cannot be certified as current PAPER ranks.

Synthetic test fixtures only. No broker authentication, orders, or deployment.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import test_cloud_paper_receipt_freshness as fixtures


IST = ZoneInfo("Asia/Kolkata")


class ExpiredContractGuardTests(unittest.TestCase):
    def run_case(self, expiry, *, expired):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "runtime"
            proof = Path(tmp) / "proof"
            runtime.mkdir()
            now = datetime.now(timezone.utc)
            stamp = now.isoformat()
            quote_stamp = now.astimezone(IST).strftime("%d-%b-%Y %H:%M:%S")
            contract = {
                "underlying": "NIFTY", "expiry": expiry,
                "strike": 24000.0, "option_type": "CE",
                "tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999",
            }
            quotes = [{
                "contract": contract,
                "quote": {
                    "tradingSymbol": "OFFLINE_TEST_ONLY", "symbolToken": "999",
                    "exchFeedTime": quote_stamp,
                    "depth": {"buy": [{"price": 100.0}], "sell": [{"price": 101.0}]},
                },
            }]
            ranking = [{
                "rank": 1, "symbol": "NIFTY", "expiry": expiry,
                "strike": 24000.0, "option_type": "CE",
                "tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999",
                "entry_bid": 100.0, "entry_ask": 101.0, "entry_price": 101.0,
                "entry_price_method": "SNAPSHOT_BEST_ASK_NOT_FILLED",
            }]

            def child(*args, **kwargs):
                fixtures.make_receipt(runtime, stamp, quotes=quotes, ranking=ranking)
                return SimpleNamespace(returncode=0)

            if expired:
                with self.assertRaisesRegex(RuntimeError, "RANK_CONTRACT_EXPIRED"):
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child)
                self.assertNotEqual(
                    json.loads((proof / "status.json").read_text())["status"],
                    "PAPER_RECEIPT_VERIFIED",
                )
            else:
                self.assertEqual(
                    fixtures.CurrentRunReceiptTests().run_once(runtime, proof, child), 0
                )

    def test_prior_ist_date_must_fail_even_when_quote_and_rank_agree(self):
        expiry = (datetime.now(IST).date() - timedelta(days=1)).isoformat()
        self.run_case(expiry, expired=True)

    def test_capture_date_expiry_is_not_prematurely_rejected(self):
        expiry = datetime.now(IST).date().isoformat()
        self.run_case(expiry, expired=False)

    def test_future_expiry_remains_valid(self):
        expiry = (datetime.now(IST).date() + timedelta(days=7)).isoformat()
        self.run_case(expiry, expired=False)


    def test_ist_midnight_boundary_uses_exchange_local_date(self):
        from cloud_runner import main as runner
        # UTC remains on Oct 24 at both instants, but IST rolls to Oct 25.
        payload = {"ranking": [{"expiry": "2026-10-24"}]}
        before = datetime.fromisoformat("2026-10-24T18:29:59+00:00")
        after = datetime.fromisoformat("2026-10-24T18:30:00+00:00")
        self.assertTrue(runner.validate_rank_expiry_against_capture(payload, before))
        with self.assertRaisesRegex(RuntimeError, "RANK_CONTRACT_EXPIRED"):
            runner.validate_rank_expiry_against_capture(payload, after)

    def test_timezone_equivalent_capture_instants_give_same_result(self):
        from cloud_runner import main as runner
        payload = {"ranking": [{"expiry": "2026-10-24"}]}
        utc = datetime.fromisoformat("2026-10-24T18:30:00+00:00")
        ist = utc.astimezone(IST)
        for stamp in (utc, ist):
            with self.subTest(stamp=stamp.isoformat()):
                with self.assertRaisesRegex(RuntimeError, "RANK_CONTRACT_EXPIRED"):
                    runner.validate_rank_expiry_against_capture(payload, stamp)


if __name__ == "__main__":
    unittest.main()
