"""Offline regression: captured instrument-master digest must bind to forecast.

Internal consistency only: this does NOT authenticate the external master source.
No broker, cloud, credentials, or real orders are used.
"""
import inspect
import unittest

from cloud_runner import main as runner

MASTER_A = "a" * 64
MASTER_B = "b" * 64


def raw(master=MASTER_A):
    return {"instrument_master_sha256": master}


def prediction(master=MASTER_A):
    return {"provenance": {"instrument_master_sha256": master}}


class InstrumentMasterProvenanceTests(unittest.TestCase):
    def test_matching_lowercase_sha256_is_accepted(self):
        self.assertTrue(runner.validate_instrument_master_provenance(
            raw(), prediction()))

    def test_mismatched_digest_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "INSTRUMENT_MASTER_PROVENANCE_MISMATCH"):
            runner.validate_instrument_master_provenance(
                raw(MASTER_A), prediction(MASTER_B))

    def test_missing_snapshot_digest_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "INSTRUMENT_MASTER_PROVENANCE_INVALID"):
            runner.validate_instrument_master_provenance(
                {}, prediction())

    def test_missing_forecast_digest_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "INSTRUMENT_MASTER_PROVENANCE_INVALID"):
            runner.validate_instrument_master_provenance(
                raw(), {"provenance": {}})

    def test_malformed_and_wrong_type_digest_fails_closed(self):
        for bad in ("short", "A" * 64, 123, None, True, "g" * 64):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(RuntimeError, "INSTRUMENT_MASTER_PROVENANCE_INVALID"):
                    runner.validate_instrument_master_provenance(
                        raw(bad), prediction())

    def test_main_checks_master_before_publishing_verified_status(self):
        source = inspect.getsource(runner.main)
        gate = "validate_instrument_master_provenance(raw_snapshot, payload)"
        self.assertIn(gate, source)
        self.assertLess(source.index(gate),
                        source.index('"status": "PAPER_RECEIPT_VERIFIED"'))


if __name__ == "__main__":
    unittest.main()
