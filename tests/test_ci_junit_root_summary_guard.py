"""JUnit testsuites root-summary integrity; offline parser regression only.

A forged root summary is not evidence that production JUnit was corrupted.
No broker, cloud, or live order operations are exercised.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "ci_skip_certification_gate.py"


def run_gate(*, root_attributes=None, suite_attributes=None):
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory) / "junit.xml"
        root = ET.Element("testsuites", **(root_attributes or {}))
        suite = ET.SubElement(
            root, "testsuite",
            **({"tests": "1", "skipped": "0", "failures": "0", "errors": "0"}
               | (suite_attributes or {})),
        )
        ET.SubElement(suite, "testcase", classname="tests.root", name="test_ok")
        ET.ElementTree(root).write(report, encoding="utf-8", xml_declaration=True)
        return subprocess.run(
            [sys.executable, str(GATE), str(report)],
            text=True, capture_output=True, check=False,
        )


class JUnitRootSummaryGuardTests(unittest.TestCase):
    def test_root_declares_skipped_but_cases_green_must_block(self):
        result = run_gate(root_attributes={"skipped": "1"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_root_declares_failure_but_cases_green_must_block(self):
        result = run_gate(root_attributes={"failures": "1"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_root_declares_error_but_cases_green_must_block(self):
        result = run_gate(root_attributes={"errors": "1"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_root_declares_zero_tests_with_case_must_block(self):
        result = run_gate(root_attributes={"tests": "0"})
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_matching_root_summary_remains_accepted(self):
        result = run_gate(root_attributes={
            "tests": "1", "skipped": "0", "failures": "0", "errors": "0",
        })
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_root_summary_remains_accepted(self):
        result = run_gate()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_subtest_inflated_root_test_count_remains_accepted(self):
        result = run_gate(root_attributes={"tests": "5"})
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
