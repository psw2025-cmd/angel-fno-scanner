"""Offline regression: published proof must equal the bytes actually verified.

Simulates a concurrent writer replacing each linked evidence file at copy time.
No broker, cloud, credentials, or real orders are involved.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cloud_runner import main as runner
from test_cloud_paper_receipt_freshness import CurrentRunReceiptTests, make_receipt
from datetime import datetime, timezone


class EvidenceCopyRaceTests(unittest.TestCase):
    def test_verified_proof_uses_validated_bytes_not_later_mutable_file_reads(self):
        for target_prefix in ("receipt.json", "entry_", "dna_"):
            with self.subTest(target_prefix=target_prefix):
                with tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    runtime, proof = root / "runtime", root / "proof"
                    runtime.mkdir()
                    expected = {}

                    def child(*args, **kwargs):
                        digest = make_receipt(runtime, datetime.now(timezone.utc).isoformat())
                        paths = (
                            runtime / "data" / "paper_ledger" / "receipt.json",
                            runtime / "data" / "paper_ledger" / ("entry_" + digest + ".json"),
                            runtime / "data" / "anomaly_logs" / ("dna_" + digest + ".json"),
                        )
                        expected.update({p.name: p.read_bytes() for p in paths})
                        return SimpleNamespace(returncode=0)

                    original_copy = shutil.copyfile

                    def racing_copy(src, dst, *args, **kwargs):
                        source = Path(src)
                        if source.name.startswith(target_prefix):
                            source.write_text('{"tampered_after_validation":true}\n', encoding="utf-8")
                        return original_copy(src, dst, *args, **kwargs)

                    with patch("shutil.copyfile", side_effect=racing_copy):
                        result = CurrentRunReceiptTests().run_once(runtime, proof, child)
                    self.assertEqual(result, 0)
                    self.assertEqual(
                        json.loads((proof / "status.json").read_text())["status"],
                        "PAPER_RECEIPT_VERIFIED",
                    )
                    for name, verified_bytes in expected.items():
                        self.assertEqual(
                            (proof / name).read_bytes(), verified_bytes,
                            "Published proof must contain the validated bytes: " + name,
                        )


if __name__ == "__main__":
    unittest.main()
