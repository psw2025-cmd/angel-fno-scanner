"""Fail-closed structural regression for reviewed Phase 2 writer parity.

The Cloud PAPER workflow must compare every directly or transitively imported
first-party executable module with reviewed main before starting a broker reader.
This test performs no broker calls, cloud writes, or real orders.
"""
import ast
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



def imported_phase2_paths(source):
    """Find first-party Phase 2 imports, including imports inside functions."""
    paths = set()
    for node in ast.walk(ast.parse(source)):
        modules = []
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        for module in modules:
            if module.startswith("phase2."):
                paths.add(module.replace(".", "/") + ".py")
    return paths


def transitive_phase2_paths():
    """Derive the current import graph instead of freezing today's module list."""
    root = WORKFLOW.parents[2]
    pending = ["run_phase2_local.py", "run_phase3_pnl.py"]
    visited = set()
    discovered = set()
    while pending:
        relative = pending.pop()
        if relative in visited:
            continue
        visited.add(relative)
        source_path = root / relative
        if not source_path.is_file():
            raise AssertionError("Missing first-party import: " + relative)
        for dependency in imported_phase2_paths(source_path.read_text(encoding="utf-8")):
            discovered.add(dependency)
            if dependency not in visited:
                pending.append(dependency)
    return discovered

class ReviewedWriterParityTests(unittest.TestCase):
    def test_all_executable_phase2_dependencies_checked_before_execution(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        missing = (REQUIRED | transitive_phase2_paths()) - parity_paths(text)
        self.assertFalse(missing, "Unreviewed writer dependency: " + ", ".join(sorted(missing)))
        self.assertLess(text.index("Verify reviewed writer parity"),
                        text.index("Execute PAPER-only cycle"))

    def test_parity_guard_rejects_drift_instead_of_warning(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('git -C paper-runtime hash-object "$path"', text)
        self.assertIn('git -C paper-runtime rev-parse "origin/main:$path"', text)
        self.assertIn('|| { echo "::error::Reviewed writer drift: $path"; exit 1; }', text)

    def test_new_import_is_discovered_for_future_regressions(self):
        synthetic_source = "def run():\n    from phase2.future_model import Model\n"
        self.assertIn("phase2/future_model.py", imported_phase2_paths(synthetic_source))

    def test_missing_critical_module_is_detectable(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for path in ("phase2/angel_readonly.py", "phase2/daily_close.py"):
            with self.subTest(path=path):
                altered = text.replace(path, "")
                self.assertIn(path, REQUIRED - parity_paths(altered))


if __name__ == "__main__":
    unittest.main()
