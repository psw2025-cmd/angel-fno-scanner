"""Offline guard: a PAPER_RECEIPT_VERIFIED forecast must contain tradeable ranked contracts.

All data is synthetic. No broker, market, cloud or real orders.
"""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests, make_receipt

from cloud_runner import main as runner


def valid_rank(rank=1):
    return {
        "rank": rank, "symbol": "NIFTY", "expiry": "2026-10-29",
        "strike": 24000.0, "option_type": "CE",
        "tradingsymbol": "OFFLINE_TEST_ONLY", "symboltoken": "999",
        "entry_bid": 100.0, "entry_ask": 101.0, "entry_price": 101.0,
        "entry_price_method": "SNAPSHOT_BEST_ASK_NOT_FILLED",
    }


class PredictionRankingContractTests(unittest.TestCase):
    def test_empty_or_wrong_type_cannot_be_verified(self):
        for value in ([], None, {}, "not-a-ranking"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "PREDICTION_RANKING_EMPTY"):
                    runner.validate_prediction_ranking({"ranking": value})

    def test_valid_quote_backed_paper_rank_passes_structural_contract(self):
        self.assertTrue(runner.validate_prediction_ranking({"ranking": [valid_rank()]}))

    def test_missing_contract_fields_or_nonfinite_strike_fail_closed(self):
        bad_rows = [
            {k: v for k, v in valid_rank().items() if k != "tradingsymbol"},
            {**valid_rank(), "strike": float("nan")},
            {**valid_rank(), "entry_price": 99.0},
            {**valid_rank(), "entry_price_method": "BROKER_FILLED"},
        ]
        for row in bad_rows:
            with self.subTest(row=row):
                with self.assertRaisesRegex(RuntimeError, "PREDICTION_RANKING_INVALID"):
                    runner.validate_prediction_ranking({"ranking": [row]})

    def test_duplicate_or_nonsequential_rank_fails_closed(self):
        for rows in ([valid_rank(), valid_rank(2)],
                     [valid_rank(2)],
                     [valid_rank(), {**valid_rank(2), "strike": 24050.0, "rank": True}]):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(RuntimeError, "PREDICTION_RANKING_INVALID"):
                    runner.validate_prediction_ranking({"ranking": rows})


    def test_full_runner_rejects_empty_ranking_despite_consistent_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, proof = root / "runtime", root / "proof"
            runtime.mkdir()
            def child(*args, **kwargs):
                # All receipt/source hashes are recalculated and consistent;
                # only the prediction has no contracts to trade.
                make_receipt(runtime, datetime.now(timezone.utc).isoformat(), ranking=[])
                return SimpleNamespace(returncode=0)
            with self.assertRaisesRegex(RuntimeError, "PREDICTION_RANKING_EMPTY"):
                CurrentRunReceiptTests().run_once(runtime, proof, child)
            status = json.loads((proof / "status.json").read_text(encoding="utf-8"))
            self.assertNotEqual(status["status"], "PAPER_RECEIPT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
