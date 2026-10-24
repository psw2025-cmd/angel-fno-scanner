"""Offline regression: --preflight must never alter a prior PAPER status.

Runs a copied runner with dummy environment values; no broker, cloud, or orders.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PreflightStatusIsolationTests(unittest.TestCase):
    def invoke(self, args, *, paper_mode="1", with_credentials=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module_dir = root / "cloud_runner"
            module_dir.mkdir()
            for name in ("main.py", "session.py", "health.py"):
                shutil.copyfile(ROOT / "cloud_runner" / name, module_dir / name)
            proof = root / "proof-output" / "cloud-paper"
            proof.mkdir(parents=True)
            status = proof / "status.json"
            original = b'{"status":"PAPER_RECEIPT_VERIFIED","prediction_hash":"old-run"}\n'
            status.write_bytes(original)
            env = os.environ.copy()
            env.update({
                "PAPER_MODE": paper_mode,
                "LIVE_ORDER_AUTHORITY": "0",
                "REAL_BROKER_ORDERS": "0",
            })
            for key in ("ANGEL_API_KEY", "ANGEL_CLIENT_CODE", "ANGEL_PIN",
                        "ANGEL_TOTP_SEED"):
                if with_credentials:
                    env[key] = "DUMMY_OFFLINE_VALUE"
                else:
                    env.pop(key, None)
            result = subprocess.run(
                [sys.executable, str(module_dir / "main.py"), *args],
                cwd=root, env=env, text=True, capture_output=True, timeout=15,
                check=False,
            )
            return result, original, status.read_bytes()

    def test_preflight_invalid_safety_flag_preserves_prior_status(self):
        result, original, after = self.invoke(["--preflight"], paper_mode="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(after, original,
                         "Failed read-only preflight must not replace run status")
        self.assertNotIn("DUMMY_OFFLINE_VALUE", result.stderr)

    def test_preflight_missing_credentials_preserves_prior_status(self):
        result, original, after = self.invoke(
            ["--preflight"], with_credentials=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(after, original)

    def test_preflight_success_preserves_prior_status(self):
        result, original, after = self.invoke(["--preflight"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, original)
        self.assertEqual(json.loads(result.stdout)["broker_authenticated"],
                         "NOT_TESTED")

    def test_once_failure_still_fails_closed(self):
        result, _, after = self.invoke(["--once"], paper_mode="0")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(after)["status"], "FAIL_CLOSED")


if __name__ == "__main__":
    unittest.main()
