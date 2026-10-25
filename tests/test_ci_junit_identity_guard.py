"""Regression: CI JUnit proof cannot double-count one collected pytest identity.

Offline XML fixtures test the certification parser only, not market/runtime proof.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "tools" / "ci_skip_certification_gate.py"


def invoke(suites):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "report.xml"
        root = ET.Element("testsuites")
        for suite_name, identities in suites:
            suite = ET.SubElement(root, "testsuite", name=suite_name,
                                  tests=str(len(identities)), skipped="0",
                                  failures="0", errors="0")
            for classname, name in identities:
                ET.SubElement(suite, "testcase", classname=classname, name=name)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return subprocess.run([sys.executable, str(GATE), str(path)],
                              capture_output=True, text=True, check=False)


class JUnitIdentityGuardTests(unittest.TestCase):
    def test_duplicate_testcase_in_one_suite_must_block(self):
        result = invoke([("pytest", [("tests.test_guard", "test_a"),
                                      ("tests.test_guard", "test_a")])])
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_duplicate_testcase_across_suites_must_block(self):
        result = invoke([("suite1", [("tests.test_guard", "test_a")]),
                         ("suite2", [("tests.test_guard", "test_a")])])
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_BLOCKED", result.stdout)

    def test_same_test_name_in_distinct_classes_is_not_a_duplicate(self):
        result = invoke([("pytest", [("tests.test_alpha", "test_shared"),
                                      ("tests.test_beta", "test_shared")])])
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_distinct_testcase_identities_still_pass_structural_gate(self):
        result = invoke([("pytest", [("tests.test_guard", "test_a"),
                                      ("tests.test_guard", "test_b")])])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("CI_TEST_GATE_PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
