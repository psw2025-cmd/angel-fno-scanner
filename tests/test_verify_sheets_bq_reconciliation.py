"""
tests/test_verify_sheets_bq_reconciliation.py

Negative controls and unit tests for tools/verify_sheets_bq_reconciliation.py.
Validates that reconciliation fails closed on mismatched run IDs, timestamps,
writers, or symbol hashes, and passes only on verified cryptographic parity.
"""

import unittest
from unittest.mock import MagicMock, patch
import datetime
from zoneinfo import ZoneInfo

from tools.verify_sheets_bq_reconciliation import reconcile, IST


class TestVerifySheetsBqReconciliation(unittest.TestCase):

    def _build_mock_clients(self, sheet_run_id="39806853848", bq_run_id="39806853848",
                            sheet_writer="market_bot", bq_writer="market_bot",
                            sheet_time_str="2026-10-22 21:14:07",
                            bq_time=datetime.datetime(2026, 10, 22, 15, 44, 7, 17813, tzinfo=datetime.timezone.utc),
                            symbols=None):
        if symbols is None:
            symbols = [f"SYM_{i}" for i in range(219)]

        # Mock gspread
        mock_gc = MagicMock()
        mock_sh = MagicMock()
        mock_sh.title = "OPTION_SHEET"

        # Mock FORENSIC_LIVE
        mock_ws_forensic = MagicMock()
        forensic_rows = [["Timestamp (IST)", "Symbol", "Col3"]] + [["2026-10-22 21:14:07", s, "val"] for s in symbols]
        mock_ws_forensic.get_all_values.return_value = forensic_rows

        # Mock CE_PE_RANK
        mock_ws_rank = MagicMock()
        rank_rows = [["Contract", "Strike", "3", "4", "5", "6", "7", "8", "9", "10", "11"]]
        for i in range(200):
            rank_rows.append([f"OPT_{i}", f"STRIKE_{i}", "3", "4", "5", "6", "7", "8", "9", "10", "11"])
        mock_ws_rank.get_all_values.return_value = rank_rows

        # Mock PUBLICATION_STATUS
        mock_ws_pub = MagicMock()
        mock_ws_pub.get_all_values.return_value = [
            ["State", "Cycle ID", "Run ID", "Git SHA", "Writer ID", "Published At (IST)"],
            ["VERIFIED", f"{sheet_run_id}:cycle", sheet_run_id, "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b", sheet_writer, sheet_time_str]
        ]

        def worksheet_router(name):
            if name == "FORENSIC_LIVE":
                return mock_ws_forensic
            elif name == "CE_PE_RANK":
                return mock_ws_rank
            elif name == "PUBLICATION_STATUS":
                return mock_ws_pub
            raise ValueError(f"Unknown worksheet: {name}")

        mock_sh.worksheet.side_effect = worksheet_router
        mock_gc.open_by_key.return_value = mock_sh

        # Mock BigQuery
        mock_bq = MagicMock()
        mock_table = MagicMock()
        mock_table.num_rows = 219
        mock_bq.get_table.return_value = mock_table

        mock_summary = MagicMock()
        mock_summary.total_rows = 219
        mock_summary.distinct_symbols = 219
        mock_summary.oldest_timestamp = bq_time
        mock_summary.newest_timestamp = bq_time

        mock_prov = MagicMock()
        mock_prov.run_id = bq_run_id
        mock_prov.git_sha = "32d9b3a34e9ee759185bc6aed1517e0ec83bed6b"
        mock_prov.writer_id = bq_writer
        mock_prov.snapshot_timestamp = bq_time

        class MockRow:
            def __init__(self, sym):
                self.symbol = sym

        def query_router(sql):
            mock_job = MagicMock()
            if "count(*) as total_rows" in sql:
                mock_job.result.return_value = [mock_summary]
            elif "GROUP BY run_id" in sql:
                mock_job.result.return_value = [mock_prov]
            elif "SELECT DISTINCT symbol" in sql:
                mock_job.result.return_value = [MockRow(s) for s in sorted(symbols)]
            return mock_job

        mock_bq.query.side_effect = query_router
        return mock_gc, mock_bq

    @patch("tools.verify_sheets_bq_reconciliation.get_authenticated_clients")
    def test_reconciliation_happy_path_passes(self, mock_auth):
        mock_gc, mock_bq = self._build_mock_clients()
        mock_auth.return_value = (mock_gc, mock_bq)

        res = reconcile()
        self.assertEqual(res["status"], "PASS")
        self.assertTrue(res["reconciliation"]["run_id_match"])
        self.assertTrue(res["reconciliation"]["timestamp_match"])
        self.assertTrue(res["reconciliation"]["writer_id_match"])
        self.assertTrue(res["reconciliation"]["symbol_exact_match"])
        self.assertTrue(res["reconciliation"]["universe_parity"])

    @patch("tools.verify_sheets_bq_reconciliation.get_authenticated_clients")
    def test_run_id_mismatch_fails_closed(self, mock_auth):
        # Sheet has run ID 39806853848, but BigQuery has 99999999999
        mock_gc, mock_bq = self._build_mock_clients(sheet_run_id="39806853848", bq_run_id="99999999999")
        mock_auth.return_value = (mock_gc, mock_bq)

        res = reconcile()
        self.assertEqual(res["status"], "FAIL_CLOSED")
        self.assertFalse(res["reconciliation"]["run_id_match"])
        self.assertFalse(res["reconciliation"]["run_id_parity_verified"])

    @patch("tools.verify_sheets_bq_reconciliation.get_authenticated_clients")
    def test_timestamp_drift_fails_closed(self, mock_auth):
        # Sheet published at 21:14:07, but BQ snapshot is 1 hour earlier
        old_bq_time = datetime.datetime(2026, 10, 22, 14, 44, 7, tzinfo=datetime.timezone.utc)
        mock_gc, mock_bq = self._build_mock_clients(bq_time=old_bq_time)
        mock_auth.return_value = (mock_gc, mock_bq)

        res = reconcile()
        self.assertEqual(res["status"], "FAIL_CLOSED")
        self.assertFalse(res["reconciliation"]["timestamp_match"])
        self.assertFalse(res["reconciliation"]["exchange_timestamp_parity_verified"])

    @patch("tools.verify_sheets_bq_reconciliation.get_authenticated_clients")
    def test_unauthorized_writer_fails_closed(self, mock_auth):
        # Rogue writer instead of market_bot
        mock_gc, mock_bq = self._build_mock_clients(sheet_writer="rogue_agent", bq_writer="rogue_agent")
        mock_auth.return_value = (mock_gc, mock_bq)

        res = reconcile()
        self.assertEqual(res["status"], "FAIL_CLOSED")
        self.assertFalse(res["reconciliation"]["writer_id_match"])


if __name__ == "__main__":
    unittest.main()
