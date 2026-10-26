"""Fail-closed validation of the Cloud PAPER registration guard's JUnit receipt.

This certifies registration and semantic tests, never a PAPER runtime.
"""
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

EXPECTED_CLASSNAME = "tests.test_cloud_paper_registration_failclosed"
SEMANTIC_CLASSNAME = "tests.test_cloud_paper_registration_contract"
SEMANTIC_EXPECTED_TESTS = frozenset({
    "test_real_registration_shell_exits_nonzero_without_orders",
    "test_semantic_guard_rejects_mutations_that_string_checks_missed[manual-only-trigger]",
    "test_semantic_guard_rejects_mutations_that_string_checks_missed[orders-disabled]",
    "test_semantic_guard_rejects_mutations_that_string_checks_missed[nonzero-exit]",
    "test_semantic_guard_rejects_mutations_that_string_checks_missed[single-step]",
    "test_semantic_guard_rejects_mutations_that_string_checks_missed[no-shell-expansion]",
    "test_semantic_guard_rejects_duplicate_yaml_keys[duplicate-trigger]",
    "test_semantic_guard_rejects_duplicate_yaml_keys[duplicate-order-flag]",
})

EXPECTED_TESTS = frozenset({
    "test_placeholder_fails_closed_instead_of_reporting_registered_success",
    "test_placeholder_is_manual_and_read_only",
    "test_placeholder_cannot_authorize_real_orders",
})


def _count(element, attribute):
    raw = element.get(attribute)
    if raw is None or not raw.isdecimal():
        raise ValueError(f"missing or invalid JUnit {element.tag}.{attribute}")
    return int(raw)


def verify(path, *, semantic=False):
    root = ET.parse(Path(path)).getroot()
    if root.tag == "testsuite":
        suites = [root]
    elif root.tag == "testsuites":
        suites = list(root)
        if not suites or any(s.tag != "testsuite" for s in suites):
            raise ValueError("invalid JUnit testsuites children")
    else:
        raise ValueError("invalid JUnit root")

    cases = []
    totals = {"tests": 0, "skipped": 0, "failures": 0, "errors": 0}
    for suite in suites:
        suite_cases = list(suite.findall("testcase"))
        allowed_children = sum(len(suite.findall(tag)) for tag in
                               ("testcase", "properties", "system-out", "system-err"))
        if len(suite) != allowed_children:
            raise ValueError("unexpected JUnit suite child")
        observed = {
            "tests": len(suite_cases),
            "skipped": sum(c.find("skipped") is not None for c in suite_cases),
            "failures": sum(c.find("failure") is not None for c in suite_cases),
            "errors": sum(c.find("error") is not None for c in suite_cases),
        }
        for key, count in observed.items():
            if _count(suite, key) != count:
                raise ValueError(f"JUnit {key} count mismatch")
            totals[key] += count
        cases.extend(suite_cases)

    for key, count in totals.items():
        if key in root.attrib and _count(root, key) != count:
            raise ValueError(f"JUnit root {key} count mismatch")

    identities = []
    allowed_case_children = {"skipped", "failure", "error", "system-out", "system-err", "properties"}
    for case in cases:
        name, classname = case.get("name", ""), case.get("classname", "")
        if not name.strip() or not classname.strip():
            raise ValueError("missing JUnit testcase identity")
        if classname != (SEMANTIC_CLASSNAME if semantic else EXPECTED_CLASSNAME):
            raise ValueError("unexpected JUnit testcase classname")
        if any(child.tag not in allowed_case_children for child in case):
            raise ValueError("unexpected JUnit testcase child")
        identities.append(name)
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate JUnit testcase identity")
    if semantic:
        if set(identities) != SEMANTIC_EXPECTED_TESTS:
            raise ValueError("semantic receipt coverage mismatch")
    elif set(identities) != EXPECTED_TESTS:
        raise ValueError("duplicate, missing, or unexpected registration tests")
    expected_total = len(SEMANTIC_EXPECTED_TESTS) if semantic else len(EXPECTED_TESTS)
    if totals != {"tests": expected_total, "skipped": 0, "failures": 0, "errors": 0}:
        raise ValueError("semantic or registration test failure or skipped case")
    return totals


def verify_semantic(path):
    """Independently certify that all eight semantic workflow cases ran."""
    return verify(path, semantic=True)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("both registration and semantic JUnit receipts are mandatory")
        counts = verify(sys.argv[1])
        semantic_counts = verify_semantic(sys.argv[2])
    except (OSError, ET.ParseError, ValueError) as exc:
        print(f"REGISTRATION_JUNIT_BLOCKED: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("REGISTRATION_JUNIT_PASS " + " ".join(f"{k}={v}" for k, v in counts.items())
          + f" semantic_tests={semantic_counts['tests']} semantic_skipped={semantic_counts['skipped']}")
