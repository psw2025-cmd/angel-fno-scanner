"""Fail-closed JUnit identity and declared-count regression tests.

These offline XML tests prove only parser behavior, not actual CI execution,
broker data, deployment, or cloud PAPER certification.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "ci_skip_certification_gate.py"


def run_gate(*, classname="tests.test_identity", name="test_case", declared_tests="1"):
    with tempfile.TemporaryDirectory() as directory:
        report = Path(directory) / "junit.xml"
        suite = ET.Element("testsuite", name="pytest", tests=declared_tests,
                           skipped="0", failures="0", errors="0")
        attributes = {}
        if classname is not None:
            attributes["classname"] = classname
        if name is not None:
            attributes["name"] = name
        ET.SubElement(suite, "testcase", **attributes)
        ET.ElementTree(suite).write(report, encoding="utf-8", xml_declaration=True)
        return subprocess.run([sys.executable, str(GATE), str(report)],
                              text=True, capture_output=True, check=False)


class RequiredJUnitIdentityTests(unittest.TestCase):
    def test_missing_classname_must_block(self):
        result = run_gate(classname=None)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_missing_name_must_block(self):
        result = run_gate(name=None)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_blank_or_whitespace_identity_must_block(self):
        for classname, name in [("", "test_case"), ("  ", "test_case"),
                                ("tests.test_identity", ""), ("tests.test_identity", "  ")]:
            with self.subTest(classname=classname, name=name):
                result = run_gate(classname=classname, name=name)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_declared_zero_tests_with_testcase_must_block(self):
        result = run_gate(declared_tests="0")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_legitimate_single_case_passes_structural_gate(self):
        result = run_gate()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
