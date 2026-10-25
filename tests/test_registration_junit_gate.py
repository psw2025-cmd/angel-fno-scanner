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


def test_unexpected_classname_rejected(tmp_path):
    def forge(root):
        root[0].findall("testcase")[0].set("classname", "tests.unrelated_suite")
    with pytest.raises(ValueError, match="unexpected"):
        verify(_xml(tmp_path, forge))


def test_unrecognized_testcase_outcome_rejected(tmp_path):
    def forge(root):
        ET.SubElement(root[0].findall("testcase")[0], "notrun")
    with pytest.raises(ValueError, match="unexpected JUnit testcase child"):
        verify(_xml(tmp_path, forge))


# Semantic safety tests are mandatory too. A green registration-only JUnit
# receipt must not mask an entirely skipped semantic workflow test suite.
def _semantic_xml(tmp_path, transform=lambda root: None):
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", tests="8", skipped="0", failures="0", errors="0")
    names = [
        "test_real_registration_shell_exits_nonzero_without_orders",
        "test_semantic_guard_rejects_mutations_that_string_checks_missed[manual-only-trigger]",
        "test_semantic_guard_rejects_mutations_that_string_checks_missed[orders-disabled]",
        "test_semantic_guard_rejects_mutations_that_string_checks_missed[nonzero-exit]",
        "test_semantic_guard_rejects_mutations_that_string_checks_missed[single-step]",
        "test_semantic_guard_rejects_mutations_that_string_checks_missed[no-shell-expansion]",
        "test_semantic_guard_rejects_duplicate_yaml_keys[duplicate-trigger]",
        "test_semantic_guard_rejects_duplicate_yaml_keys[duplicate-order-flag]",
    ]
    for name in names:
        ET.SubElement(suite, "testcase", classname="tests.test_cloud_paper_registration_contract", name=name)
    transform(root)
    path = tmp_path / "semantic-receipt.xml"
    ET.ElementTree(root).write(path, encoding="utf-8")
    return path


def test_semantic_receipt_requires_eight_distinct_cases(tmp_path):
    from tools import registration_junit_gate as gate
    assert gate.verify_semantic(_semantic_xml(tmp_path))["tests"] == 8


def test_semantic_receipt_rejects_skipped_case(tmp_path):
    from tools import registration_junit_gate as gate
    def forge(root):
        ET.SubElement(root[0][0], "skipped")
        root[0].set("skipped", "1")
    with pytest.raises(ValueError, match="skipped"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))


def test_semantic_receipt_rejects_missing_case(tmp_path):
    from tools import registration_junit_gate as gate
    def forge(root):
        root[0].remove(root[0][-1])
        root[0].set("tests", "7")
    with pytest.raises(ValueError, match="coverage"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))


def test_semantic_receipt_rejects_duplicate_case(tmp_path):
    from tools import registration_junit_gate as gate
    def forge(root):
        cases = root[0].findall("testcase")
        cases[1].set("name", cases[2].get("name"))
    with pytest.raises(ValueError, match="duplicate"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))


def test_semantic_receipt_rejects_unrelated_case(tmp_path):
    from tools import registration_junit_gate as gate
    def forge(root):
        root[0][0].set("name", "test_unrelated")
    with pytest.raises(ValueError, match="coverage"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))


def test_semantic_receipt_rejects_contradictory_root_count(tmp_path):
    from tools import registration_junit_gate as gate
    with pytest.raises(ValueError, match="root tests"):
        gate.verify_semantic(_semantic_xml(tmp_path, lambda root: root.set("tests", "9")))


def test_semantic_receipt_rejects_unexpected_parameter_identity(tmp_path):
    """A matching count is not proof that the five required mutations ran."""
    from tools import registration_junit_gate as gate

    def forge(root):
        root[0].findall("testcase")[1].set(
            "name", "test_semantic_guard_rejects_mutations_that_string_checks_missed[unverified-case]"
        )

    with pytest.raises(ValueError, match="coverage"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))


def test_semantic_receipt_rejects_unexpected_duplicate_key_parameter(tmp_path):
    """Two arbitrary parameter IDs must not satisfy duplicate-key coverage."""
    from tools import registration_junit_gate as gate

    def forge(root):
        root[0].findall("testcase")[-1].set(
            "name", "test_semantic_guard_rejects_duplicate_yaml_keys[unverified-key]"
        )

    with pytest.raises(ValueError, match="coverage"):
        gate.verify_semantic(_semantic_xml(tmp_path, forge))
