"""Offline regression: no skipped pytest case can produce a certified CI green.

This checks JUnit XML only; it does not claim cloud deployment or broker proof.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "ci_skip_certification_gate.py"


class CISkipCertificationGateTests(unittest.TestCase):
    def run_gate(self, *, statuses=("passed",), malformed=False, missing=False):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pytest.xml"
            if not missing:
                if malformed:
                    report.write_text("<testsuite>", encoding="utf-8")
                else:
                    suite = ET.Element("testsuite", tests=str(len(statuses)))
                    for index, status in enumerate(statuses):
                        case = ET.SubElement(suite, "testcase", name=f"case_{index}")
                        if status != "passed":
                            ET.SubElement(case, status, message=status)
                    ET.ElementTree(suite).write(report, encoding="utf-8", xml_declaration=True)
            return subprocess.run(
                [sys.executable, str(GUARD), str(report)],
                text=True, capture_output=True, check=False
            )

    def test_complete_non_skipped_suite_can_pass_structural_gate(self):
        result = self.run_gate(statuses=("passed", "passed"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CI_TEST_GATE_PASS", result.stdout)

    def test_any_skip_blocks_certification_even_if_all_other_tests_pass(self):
        result = self.run_gate(statuses=("passed", "skipped", "passed"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)
        self.assertIn("skipped=1", result.stdout)

    def test_failures_and_errors_block(self):
        for status in ("failure", "error"):
            with self.subTest(status=status):
                result = self.run_gate(statuses=("passed", status))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_missing_or_malformed_report_blocks(self):
        for args in ({"missing": True}, {"malformed": True}):
            with self.subTest(args=args):
                result = self.run_gate(**args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_zero_collected_cases_blocks(self):
        result = self.run_gate(statuses=())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_pytest_subtest_count_metadata_does_not_hide_case_level_result(self):
        # pytest/unittest subtests can inflate suite totals without separate
        # testcase nodes. Case-level skipped/failure/error markers are decisive.
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pytest.xml"
            suite = ET.Element("testsuite", tests="5")
            ET.SubElement(suite, "testcase", name="one_collected_case")
            ET.ElementTree(suite).write(report, encoding="utf-8")
            result = subprocess.run([sys.executable, str(GUARD), str(report)],
                                    text=True, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_inconsistent_skipped_metadata_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "pytest.xml"
            suite = ET.Element("testsuite", tests="1", skipped="0")
            case = ET.SubElement(suite, "testcase", name="skipped_case")
            ET.SubElement(case, "skipped")
            ET.ElementTree(suite).write(report, encoding="utf-8")
            result = subprocess.run([sys.executable, str(GUARD), str(report)],
                                    text=True, capture_output=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_workflow_must_invoke_gate_after_generating_junit(self):
        workflow = (ROOT / ".github/workflows/cloud-paper-safety-ci.yml").read_text(encoding="utf-8")
        self.assertIn("--junitxml=", workflow)
        self.assertIn("python tools/ci_skip_certification_gate.py", workflow)


if __name__ == "__main__":
    unittest.main()
