"""Offline regression: a rejected --once startup must not leave a prior verified status.

No broker calls, cloud access, credentials, or real orders.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cloud_runner import main as runner


class StartupStatusInvalidationTests(unittest.TestCase):
    def test_preflight_failures_invalidate_prior_verified_status(self):
        for failure in ("invalid_environment", "wrong_runtime_branch", "unreviewed_env_file"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                runtime = root / "runtime"
                runtime.mkdir()
                proof = root / "proof"
                proof.mkdir()
                status = proof / "status.json"
                status.write_text(json.dumps({
                    "status": "PAPER_RECEIPT_VERIFIED",
                    "prediction_hash": "old-session-not-current",
                }), encoding="utf-8")
                if failure == "unreviewed_env_file":
                    (runtime / ".env").write_text("", encoding="utf-8")
                flags = {
                    "PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0",
                    "REAL_BROKER_ORDERS": "0",
                    "CLOUD_PAPER_RUNTIME_DIR": str(runtime),
                }
                env_error = (RuntimeError("INVALID_ENVIRONMENT")
                             if failure == "invalid_environment" else None)
                branch = ("other-branch" if failure == "wrong_runtime_branch"
                          else "test-framework")
                expected = {
                    "invalid_environment": "INVALID_ENVIRONMENT",
                    "wrong_runtime_branch": "WRITE_GUARD",
                    "unreviewed_env_file": "UNREVIEWED_ENV_FILE_IN_CHILD_RUNTIME",
                }[failure]
                with patch.dict(os.environ, flags, clear=True):
                    with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                        with patch.object(runner, "PROOF", proof):
                            with patch.object(runner, "validate_environment",
                                              side_effect=env_error):
                                with patch.object(runner, "git", return_value=branch):
                                    with patch.object(runner.subprocess, "run",
                                                      side_effect=AssertionError("child must not run")):
                                        with self.assertRaisesRegex(RuntimeError, expected):
                                            runner.main()
                self.assertEqual(
                    json.loads(status.read_text(encoding="utf-8"))["status"],
                    "RUNNING_NOT_VERIFIED",
                    "Rejected startup must invalidate stale success before any guard can fail",
                )


if __name__ == "__main__":
    unittest.main()
