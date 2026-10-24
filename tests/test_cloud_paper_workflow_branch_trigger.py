"""Prevent silent loss of direct-head PAPER CI on newly owned fix branches.

This is a workflow-routing contract test, not evidence that CI ran.
"""
import fnmatch
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cloud-paper-safety-ci.yml"


def push_branch_patterns(text):
    match = re.search(r"(?m)^  push:\s*\n    branches:\s*\[([^\]]+)\]", text)
    if not match:
        raise AssertionError("Cloud PAPER Safety CI push branch trigger missing")
    return [value.strip().strip("'\"") for value in match.group(1).split(",")]


def triggered(branch, patterns):
    return any(fnmatch.fnmatchcase(branch, pattern) for pattern in patterns)


class CloudPaperBranchTriggerTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.patterns = push_branch_patterns(self.text)

    def test_new_owned_paper_fix_branches_get_direct_head_ci(self):
        self.assertIn("fix/cloud-paper-*", self.patterns)
        for branch in (
            "fix/cloud-paper-ci-branch-coverage-20261024",
            "fix/cloud-paper-future-safety-20270101",
            "fix/cloud-paper-preflight-status-isolation-20261024",
        ):
            with self.subTest(branch=branch):
                self.assertTrue(triggered(branch, self.patterns), branch)

    def test_runner_branch_kept_and_unrelated_branches_excluded(self):
        self.assertTrue(triggered("feat/cloud-paper-runner", self.patterns))
        for branch in ("feat/phase5-learning-engine", "fix/unrelated", "main"):
            with self.subTest(branch=branch):
                self.assertFalse(triggered(branch, self.patterns), branch)

    def test_trigger_is_bounded_not_manual_enumeration(self):
        self.assertLessEqual(len(self.patterns), 3)
        self.assertIn("  workflow_dispatch:", self.text)
        self.assertIn("  pull_request:", self.text)

    def test_exact_checkout_identity_guard_preserved(self):
        self.assertIn('test "$actual" = "$GITHUB_SHA"', self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("REAL_BROKER_ORDERS: '0'", self.text)


if __name__ == "__main__":
    unittest.main()
