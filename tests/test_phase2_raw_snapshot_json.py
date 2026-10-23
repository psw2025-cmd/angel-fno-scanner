"""Offline regression for Phase 2 raw broker snapshot JSON serialization.

The production writer must emit JSON that json.load can read. No broker access.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from run_phase2_local import serialize_raw_snapshot


class RawSnapshotJsonContractTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "source_kind": "ANGEL_SMARTAPI_READONLY_QUOTES_NOT_OFFICIAL_SETTLEMENT",
            "captured_at": "2026-10-23T15:14:00+05:30",
            "quotes": [{"contract": {"tradingsymbol": "OFFLINE_TEST_ONLY"},
                        "quote": {"tradingSymbol": "OFFLINE_TEST_ONLY"}}],
        }

    def test_roundtrip_through_real_file_and_json_load(self):
        text = serialize_raw_snapshot(self.snapshot)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "raw_snapshot.json"
            path.write_text(text, encoding="utf-8")
            with path.open(encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), self.snapshot)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )

    def test_exactly_one_real_terminal_newline_not_literal_backslash_n(self):
        text = serialize_raw_snapshot(self.snapshot)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_nonfinite_broker_values_fail_closed(self):
        invalid = {**self.snapshot, "quotes": [{"quote": {"price": float("nan")}}]}
        with self.assertRaises(ValueError):
            serialize_raw_snapshot(invalid)


if __name__ == "__main__":
    unittest.main()
