"""
tests/test_verify_codex1_gates.py
Tests negative controls and edge cases for verify_codex1_gates validators using
dependency and fixture injection into the actual validation functions.
"""
import tempfile
import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.verify_codex1_gates import (
    validate_gate1_processes,
    validate_gate2_broker,
    validate_gate3_bigquery,
    validate_gate4_safety_and_freshness,
    get_utc_now
)

class TestVerifyCodex1GatesNegativeControls(unittest.TestCase):

    # -------------------------------------------------------------
    # GATE 1 NEGATIVE CONTROLS
    # -------------------------------------------------------------
    def test_gate1_ready_alone_is_not_running(self):
        """Task Scheduler state 'Ready' without running dedicated PID must FAIL."""
        procs = []  # No dedicated process running
        task_state = "Ready"  # Ready alone is NOT running
        res = validate_gate1_processes(procs_fixture=procs, task_state_fixture=task_state)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("Ready alone is not running", res["reason"])

    def test_gate1_generic_python_rejected(self):
        """Generic python process without scanner script must FAIL."""
        procs = [
            {"ProcessId": 9999, "CommandLine": "python.exe generic_worker.py"},
            {"ProcessId": 9998, "CommandLine": "C:\\Python\\pythonw.exe daemon.py"}
        ]
        task_state = "Disabled"
        res = validate_gate1_processes(procs_fixture=procs, task_state_fixture=task_state)
        self.assertEqual(res["status"], "FAIL")

    def test_gate1_dedicated_supervisor_accepted(self):
        """Active universal_supervisor.py PID must PASS."""
        procs = [
            {"ProcessId": 1234, "CommandLine": "python.exe C:\\path\\universal_supervisor.py --interval 60"}
        ]
        res = validate_gate1_processes(procs_fixture=procs, task_state_fixture="Running")
        self.assertEqual(res["status"], "PASS")
        self.assertIn(1234, res["supervisor_pids"])

    # -------------------------------------------------------------
    # GATE 2 NEGATIVE CONTROLS
    # -------------------------------------------------------------
    def test_gate2_broker_http_500_fails(self):
        """Broker returning HTTP 500 must FAIL."""
        resp = {
            "Angel One SmartAPI": {"status_code": 500, "latency_ms": 120.0},
            "Dhan API": {"status_code": 200, "latency_ms": 80.0}
        }
        res = validate_gate2_broker(responses_fixture=resp)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["endpoints"]["Angel One SmartAPI"]["status"], "FAIL")

    def test_gate2_broker_network_error_fails(self):
        """Broker network connection timeout must FAIL."""
        resp = {
            "Angel One SmartAPI": {"error": "Connection timed out", "latency_ms": 7000.0}
        }
        res = validate_gate2_broker(responses_fixture=resp)
        self.assertEqual(res["status"], "FAIL")

    # -------------------------------------------------------------
    # GATE 3 NEGATIVE CONTROLS
    # -------------------------------------------------------------
    def test_gate3_wrong_row_count_fails(self):
        """Row count not equal to 219 must FAIL."""
        rows = [{"symbol": f"SYM_{i}", "rank": i} for i in range(218)]  # Only 218 rows
        res = validate_gate3_bigquery(rows_fixture=rows, universe_path=None)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["total_rows"], 218)

    def test_gate3_duplicate_symbols_fails(self):
        """Duplicate symbols (219 rows with only 218 unique symbols) must FAIL."""
        rows = [{"symbol": f"SYM_{i}", "rank": i} for i in range(218)]
        rows.append({"symbol": "SYM_0", "rank": 219})  # Duplicate SYM_0
        self.assertEqual(len(rows), 219)
        res = validate_gate3_bigquery(rows_fixture=rows, universe_path=None)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(res["duplicates"], 1)

    def test_gate3_null_symbols_fails(self):
        """Null or empty symbol values must FAIL."""
        rows = [{"symbol": f"SYM_{i}", "rank": i} for i in range(218)]
        rows.append({"symbol": None, "rank": 219})
        res = validate_gate3_bigquery(rows_fixture=rows, universe_path=None)
        self.assertEqual(res["status"], "FAIL")

    # -------------------------------------------------------------
    # GATE 4 NEGATIVE CONTROLS
    # -------------------------------------------------------------
    def test_gate4_missing_safety_fails_no_default(self):
        """Missing PAPER_MODE or LIVE_ORDER_AUTHORITY must FAIL without defaulting."""
        env = {}  # Empty environment
        res = validate_gate4_safety_and_freshness(env_fixture=env)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("cannot default", res["reason"])

    def test_gate4_live_order_authority_1_fails(self):
        """LIVE_ORDER_AUTHORITY=1 must FAIL."""
        env = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "1"}
        res = validate_gate4_safety_and_freshness(env_fixture=env)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("LIVE_ORDER_AUTHORITY", res["reason"])

    def test_gate4_paper_mode_0_fails(self):
        """PAPER_MODE=0 must FAIL."""
        env = {"PAPER_MODE": "0", "LIVE_ORDER_AUTHORITY": "0"}
        res = validate_gate4_safety_and_freshness(env_fixture=env)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("PAPER_MODE", res["reason"])

    def test_gate4_future_timestamp_fails(self):
        """Sync timestamp in the future must FAIL."""
        env = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0"}
        future_time = (get_utc_now() + timedelta(hours=2)).isoformat()
        ev = {"sync_utc": future_time}
        res = validate_gate4_safety_and_freshness(env_fixture=env, evidence_fixture=ev)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("Future sync timestamp", res["reason"])

    def test_gate4_stale_timestamp_fails(self):
        """Sync timestamp older than 60 minutes must FAIL."""
        env = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0"}
        stale_time = (get_utc_now() - timedelta(minutes=90)).isoformat()
        ev = {"sync_utc": stale_time}
        res = validate_gate4_safety_and_freshness(env_fixture=env, evidence_fixture=ev)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("stale", res["reason"].lower())

    def test_gate1_holiday_missing_scanner_is_quiet(self):
        """A holiday with no PID is expected quiet, not a scanner failure."""
        res = validate_gate1_processes(procs_fixture=[], task_state_fixture="Ready", session_status="HOLIDAY")
        self.assertEqual(res["status"], "EXPECTED_QUIET")

    def test_gate3_after_close_does_not_require_today(self):
        res = validate_gate3_bigquery(rows_fixture=None, universe_path=None, session_status="AFTER_CLOSE")
        self.assertEqual(res["status"], "NOT_REQUIRED")

    def test_gate4_stale_on_holiday_is_not_a_failure(self):
        """90 minutes old is a failure only while the session is OPEN."""
        env = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0"}
        stale_time = (get_utc_now() - timedelta(minutes=90)).isoformat()
        res = validate_gate4_safety_and_freshness(
            env_fixture=env, evidence_fixture={"sync_utc": stale_time}, session_status="HOLIDAY"
        )
        self.assertEqual(res["status"], "NOT_REQUIRED")
        self.assertNotEqual(res["status"], "PASS")

    def test_gate4_malformed_timestamp_fails(self):
        """Malformed timestamp string must FAIL."""
        env = {"PAPER_MODE": "1", "LIVE_ORDER_AUTHORITY": "0"}
        ev = {"sync_utc": "not-a-valid-timestamp"}
        res = validate_gate4_safety_and_freshness(env_fixture=env, evidence_fixture=ev)
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("Malformed sync_utc", res["reason"])

    def test_gate4_missing_deployed_file_fails(self):
        """A missing deployed safety file fails even when the process env is empty."""
        missing = REPO_ROOT / "does-not-exist-safety.env"
        res = validate_gate4_safety_and_freshness(
            safety_path=missing, process_env={}, session_status="HOLIDAY"
        )
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("missing", res["reason"])
        self.assertTrue(str(res.get("source", "")).startswith("missing_file:"))

    def test_gate4_deployed_file_live_authority_1_fails(self):
        """A deployed file with LIVE_ORDER_AUTHORITY=1 fails closed."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "safety.env"
            path.write_text("PAPER_MODE=1\nLIVE_ORDER_AUTHORITY=1\n", encoding="utf-8")
            res = validate_gate4_safety_and_freshness(
                safety_path=path, process_env={}, session_status="HOLIDAY"
            )
        self.assertEqual(res["status"], "FAIL")
        self.assertIn("LIVE_ORDER_AUTHORITY", res["reason"])
        self.assertNotEqual(res["status"], "PASS")

    def test_gate4_correct_file_allows_empty_process_env(self):
        """Empty process environment does not fail a correct deployed file."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "safety.env"
            path.write_text("PAPER_MODE=1\nLIVE_ORDER_AUTHORITY=0\n", encoding="utf-8")
            res = validate_gate4_safety_and_freshness(
                safety_path=path, process_env={}, session_status="HOLIDAY"
            )
        self.assertEqual(res["status"], "NOT_REQUIRED")
        self.assertEqual(res["paper_mode"], "1")
        self.assertEqual(res["live_order_authority"], "0")
        self.assertIn("deployed_file:", res["source"])

if __name__ == "__main__":
    unittest.main()
