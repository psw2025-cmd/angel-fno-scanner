"""Fail-closed structural regression for reviewed Phase 2 writer parity.

The Cloud PAPER workflow must compare every directly or transitively imported
first-party executable module with reviewed main before starting a broker reader.
This test performs no broker calls, cloud writes, or real orders.
"""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cloud-paper-runner.yml"

REQUIRED = frozenset({
    "run_phase2_local.py",
    "run_phase3_pnl.py",
    "update_phase4_dashboard.py",
    "nse_calendar.py",
    "nse_holidays.json",
    "phase2/angel_instruments.py",
    "phase2/angel_readonly.py",
    "phase2/option_stream.py",
    "phase2/model.py",
    "phase2/heuristic.py",
    "phase2/daily_close.py",
    "phase2/local_publisher.py",
    "phase2/option_dna.py",
})


def parity_paths(text):
    match = re.search(r"for path in ([^\n]+); do", text)
    if match is None:
        return frozenset()
    return frozenset(match.group(1).split())


class ReviewedWriterParityTests(unittest.TestCase):
    def test_all_executable_phase2_dependencies_checked_before_execution(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        missing = REQUIRED - parity_paths(text)
        self.assertFalse(missing, "Unreviewed writer dependency: " + ", ".join(sorted(missing)))
        self.assertLess(text.index("Verify reviewed writer parity"),
                        text.index("Execute PAPER-only cycle"))

    def test_parity_guard_rejects_drift_instead_of_warning(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('git -C paper-runtime hash-object "$path"', text)
        self.assertIn('git -C paper-runtime rev-parse "origin/main:$path"', text)
        self.assertIn('|| { echo "::error::Reviewed writer drift: $path"; exit 1; }', text)

    def test_missing_critical_module_is_detectable(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for path in ("phase2/angel_readonly.py", "phase2/daily_close.py"):
            with self.subTest(path=path):
                altered = text.replace(path, "")
                self.assertIn(path, REQUIRED - parity_paths(altered))


if __name__ == "__main__":
    unittest.main()
