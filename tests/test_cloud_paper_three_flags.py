"""Offline, no-network safety tests for the draft cloud PAPER runner."""
import contextlib
import fnmatch
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cloud_runner import main as cloud_main
from cloud_runner.health import snapshot
from cloud_runner.session import enforce_safety, validate_environment

ROOT = Path(__file__).resolve().parents[1]
FLAGS = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0", "REAL_BROKER_ORDERS": "0"}
FAKE_CREDS = {
    "ANGEL_API_KEY": "DUMMY_NOT_A_SECRET",
    "ANGEL_CLIENT_CODE": "DUMMY_NOT_A_CLIENT",
    "ANGEL_PIN": "DUMMY_NOT_A_PIN",
    "ANGEL_TOTP_SEED": "DUMMY_NOT_A_TOTP",
}


class CloudPaperSafetyTests(unittest.TestCase):
    def test_exact_three_flags_accepted(self):
        with patch.dict(os.environ, FLAGS, clear=True):
            enforce_safety()

    def test_missing_each_flag_fails_closed(self):
        for name in FLAGS:
            with self.subTest(missing=name):
                with patch.dict(os.environ, {k: v for k, v in FLAGS.items() if k != name}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PAPER-only"):
                        enforce_safety()

    def test_invalid_each_flag_fails_closed(self):
        for name in FLAGS:
            with self.subTest(invalid=name):
                with patch.dict(os.environ, {**FLAGS, name: "1" if name != "PAPER_MODE" else "0"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "PAPER-only"):
                        enforce_safety()

    def test_preflight_rejects_absent_credentials_after_safety(self):
        with patch.dict(os.environ, FLAGS, clear=True):
            with self.assertRaisesRegex(RuntimeError, "ANGEL_API_KEY"):
                validate_environment()

    def test_preflight_is_not_authentication_proof(self):
        with patch.dict(os.environ, {**FLAGS, **FAKE_CREDS}, clear=True):
            with patch.object(sys, "argv", ["cloud_runner/main.py", "--preflight"]):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(cloud_main.main(), 0)
            result = json.loads(output.getvalue())
            self.assertFalse(result["real_broker_orders"])
            self.assertEqual(result["broker_authenticated"], "NOT_TESTED")
            self.assertEqual(result["tick_freshness"], "NOT_TESTED")
            self.assertNotIn(FAKE_CREDS["ANGEL_PIN"], output.getvalue())

    def test_child_inherits_three_flags_without_broker_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {**FLAGS, **FAKE_CREDS, "CLOUD_PAPER_RUNTIME_DIR": tmp}, clear=True):
                with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                    with patch.object(cloud_main, "git", return_value="test-framework"):
                        with patch.object(cloud_main.subprocess, "run", return_value=SimpleNamespace(returncode=23)) as run:
                            self.assertEqual(cloud_main.main(), 23)
            kwargs = run.call_args.kwargs
            self.assertEqual(kwargs["env"]["REAL_BROKER_ORDERS"], "0")
            self.assertEqual(kwargs["env"]["PAPER_MODE"], "1")
            self.assertEqual(kwargs["env"]["LIVE_ORDER_AUTHORITY"], "0")
            self.assertEqual(kwargs["env"]["PAPER_LEDGER_BRANCH"], "test-framework")

    def test_stuck_child_times_out_and_records_fail_closed(self):
        """A hung child must not hold the scheduler indefinitely or leave RUNNING status."""
        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "proof"
            with patch.dict(os.environ, {**FLAGS, **FAKE_CREDS, "CLOUD_PAPER_RUNTIME_DIR": tmp}, clear=True):
                with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                    with patch.object(cloud_main, "PROOF", proof):
                        with patch.object(cloud_main, "git", return_value="test-framework"):
                            with patch.object(cloud_main.subprocess, "run",
                                              side_effect=cloud_main.subprocess.TimeoutExpired(
                                                  cmd=["python", "run_phase2_local.py"], timeout=600)) as run:
                                self.assertEqual(cloud_main.main(), 124)
                                self.assertEqual(run.call_args.kwargs["timeout"], 600)
            status = json.loads((proof / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "FAIL_CLOSED")
            self.assertEqual(status["error_type"], "CHILD_TIMEOUT")
            self.assertEqual(status["child_exit_code"], 124)
            self.assertEqual(status["broker_order_audit"], "NOT_PERFORMED")

    def test_child_env_file_override_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".env").write_text("REAL_BROKER_ORDERS=1\n", encoding="utf-8")
            with patch.dict(os.environ, {**FLAGS, **FAKE_CREDS, "CLOUD_PAPER_RUNTIME_DIR": tmp}, clear=True):
                with patch.object(sys, "argv", ["cloud_runner/main.py", "--once"]):
                    with patch.object(cloud_main, "git", return_value="test-framework"):
                        with patch.object(cloud_main.subprocess, "run") as run:
                            with self.assertRaisesRegex(RuntimeError, "UNREVIEWED_ENV_FILE"):
                                cloud_main.main()
                            run.assert_not_called()

    def test_workflow_explicitly_disables_real_orders(self):
        workflow = (ROOT / ".github/workflows/cloud-paper-runner.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^\s+REAL_BROKER_ORDERS: '0'\s*$")
        self.assertIn("PAPER_MODE: '1'", workflow)
        self.assertIn("LIVE_ORDER_AUTHORITY: '0'", workflow)

    def test_safety_ci_persists_after_peer_integration(self):
        workflow = (ROOT / ".github/workflows/cloud-paper-safety-ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main, feat/cloud-paper-runner]", workflow)
        push_section = workflow.split("  push:", 1)[1].split("  pull_request:", 1)[0]
        match = re.search(r"branches:\s*\[([^\]]+)\]", push_section)
        self.assertIsNotNone(match)
        push_patterns = {name.strip().strip("'\\\"") for name in match.group(1).split(",")}
        self.assertIn("feat/cloud-paper-runner", push_patterns)
        for branch in ("fix/cloud-paper-third-flag-20261023",
                       "fix/cloud-paper-ci-branch-coverage-20261024",
                       "fix/cloud-paper-future-safety-20270101"):
            with self.subTest(branch=branch):
                self.assertTrue(any(fnmatch.fnmatchcase(branch, pattern)
                                    for pattern in push_patterns), branch)

    def test_evidence_never_asserts_unobserved_no_order_execution(self):
        source = (ROOT / "cloud_runner/main.py").read_text(encoding="utf-8")
        self.assertIn('"broker_order_audit": "NOT_PERFORMED"', source)
        self.assertNotIn('"broker_order_executed": False', source)


if __name__ == "__main__":
    unittest.main()
