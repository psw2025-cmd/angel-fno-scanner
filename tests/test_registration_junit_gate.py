"""Negative and positive receipt tests for the registration-only guard."""
from xml.etree import ElementTree as ET

import pytest

from tools.registration_junit_gate import EXPECTED_TESTS, verify


def _xml(tmp_path, transform=lambda root: None):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests="3", skipped="0", failures="0", errors="0")
    for name in sorted(EXPECTED_TESTS):
        ET.SubElement(suite, "testcase", classname="tests.test_cloud_paper_registration_failclosed", name=name)
    transform(root)
    path = tmp_path / "receipt.xml"
    ET.ElementTree(root).write(path, encoding="utf-8")
    return path


def test_valid_three_unique_cases(tmp_path):
    assert verify(_xml(tmp_path))["tests"] == 3


def test_duplicate_name_inflates_false_green(tmp_path):
    def forge(root):
        cases = root[0].findall("testcase")
        cases[1].set("name", cases[0].get("name"))
    with pytest.raises(ValueError, match="duplicate"):
        verify(_xml(tmp_path, forge))


def test_missing_expected_case_replaced_with_unrelated(tmp_path):
    def forge(root):
        root[0].findall("testcase")[1].set("name", "test_unrelated")
    with pytest.raises(ValueError, match="unexpected"):
        verify(_xml(tmp_path, forge))


def test_declared_count_contradiction(tmp_path):
    with pytest.raises(ValueError, match="count mismatch"):
        verify(_xml(tmp_path, lambda root: root[0].set("tests", "4")))


def test_root_count_contradiction(tmp_path):
    with pytest.raises(ValueError, match="root tests"):
        verify(_xml(tmp_path, lambda root: root.set("tests", "9")))


def test_skipped_case(tmp_path):
    def forge(root):
        ET.SubElement(root[0][0], "skipped")
        root[0].set("skipped", "1")
    with pytest.raises(ValueError, match="skipped"):
        verify(_xml(tmp_path, forge))


def test_missing_classname(tmp_path):
    def forge(root):
        del root[0][0].attrib["classname"]
    with pytest.raises(ValueError, match="identity"):
        verify(_xml(tmp_path, forge))


def test_malformed_xml(tmp_path):
    path = tmp_path / "receipt.xml"
    path.write_text("<testsuites><testsuite>", encoding="utf-8")
    with pytest.raises(ET.ParseError):
        verify(path)
