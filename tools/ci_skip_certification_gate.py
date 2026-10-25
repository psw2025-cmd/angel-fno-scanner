#!/usr/bin/env python3
"""Fail closed if the repository pytest JUnit report has skipped/failed tests.

A structural CI pass is not production certification. This gate checks only
the collected test outcome, not cloud deployment or broker authentication.
"""
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def assess_report(path):
    try:
        root = ET.parse(path).getroot()
        if root.tag not in ("testsuite", "testsuites"):
            raise ValueError("unexpected JUnit root")
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        if not suites:
            raise ValueError("no JUnit test suites")
        cases = list(root.iter("testcase"))
        if not cases:
            raise ValueError("zero collected test cases")
        # One JUnit testcase identity must represent at most one collected test.
        # Without this check a repeated passing case can inflate the denominator.
        # JUnit testcase 'name' is required, while 'classname' is optional.
        # An empty name can otherwise be counted as a successful collected test.
        if any(not (case.get("name") or "").strip() for case in cases):
            raise ValueError("missing or blank JUnit testcase name")
        identities = [(case.get("classname", ""), case.get("name", ""))
                      for case in cases]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate JUnit testcase identity")
        for suite in suites:
            # pytest reports one suite; reject inconsistent aggregate metadata.
            direct = list(suite.findall("testcase"))
            # Pytest/unittest subtests may increase declared totals without
            # emitting additional testcase nodes. Only the lower bound is safe.
            declared_tests = suite.get("tests")
            if declared_tests is not None and int(declared_tests) < len(direct):
                raise ValueError("JUnit suite test count below testcase count")
            for attribute, observed in (
                # pytest may count unittest subtests in suite totals without
                # emitting a testcase element for each subtest.
                ("skipped", sum(c.find("skipped") is not None for c in direct)),
                ("failures", sum(c.find("failure") is not None for c in direct)),
                ("errors", sum(c.find("error") is not None for c in direct)),
            ):
                declared = suite.get(attribute)
                if declared is not None and int(declared) != observed:
                    raise ValueError("inconsistent JUnit " + attribute)
        # The optional aggregate <testsuites> counters must not contradict
        # testcase evidence. Pytest may report additional unittest subtests,
        # so the declared test total is a lower-bound check, not equality.
        if root.tag == "testsuites":
            declared_tests = root.get("tests")
            if declared_tests is not None and int(declared_tests) < len(cases):
                raise ValueError("JUnit root test count below testcase count")
            for attribute, observed in (
                ("skipped", sum(c.find("skipped") is not None for c in cases)),
                ("failures", sum(c.find("failure") is not None for c in cases)),
                ("errors", sum(c.find("error") is not None for c in cases)),
            ):
                declared = root.get(attribute)
                if declared is not None and int(declared) != observed:
                    raise ValueError("inconsistent JUnit root " + attribute)
        skipped = sum(case.find("skipped") is not None for case in cases)
        failed = sum(case.find("failure") is not None for case in cases)
        errors = sum(case.find("error") is not None for case in cases)
        return len(cases), skipped, failed, errors
    except (OSError, ET.ParseError, ValueError, TypeError) as exc:
        print("CI_TEST_GATE_BLOCKED invalid_or_missing_junit=" + type(exc).__name__ + " detail=" + str(exc))
        return None


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("CI_TEST_GATE_BLOCKED expected_one_junit_path")
        return 2
    counts = assess_report(Path(args[0]))
    if counts is None:
        return 2
    total, skipped, failed, errors = counts
    message = f"tests={total} skipped={skipped} failures={failed} errors={errors}"
    if skipped or failed or errors:
        print("CI_TEST_GATE_BLOCKED " + message)
        return 1
    print("CI_TEST_GATE_PASS " + message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
