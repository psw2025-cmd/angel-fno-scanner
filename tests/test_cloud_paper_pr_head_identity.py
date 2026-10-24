"""Regression contract: PAPER safety CI must test the PR head, not only GitHub's synthetic merge ref.

No network, broker, cloud, or order calls.  A passing fixture is not a CI receipt.
"""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/cloud-paper-safety-ci.yml"


class CloudPaperPrHeadIdentityTests(unittest.TestCase):
    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_checkout_explicitly_targets_pr_head_with_push_fallback(self):
        checkout = self.text.split("- name: Checkout exact event revision", 1)[1].split(
            "- name: Verify checkout identity", 1
        )[0]
        self.assertRegex(
            checkout,
            r"(?m)^\s+ref:\s*\$\{\{\s*github\.event\.pull_request\.head\.sha\s*\|\|\s*github\.sha\s*\}\}\s*$",
        )
        self.assertIn("persist-credentials: false", checkout)

    def test_identity_assertion_uses_expected_pr_head_not_event_merge_sha(self):
        step = self.text.split("- name: Verify checkout identity", 1)[1].split(
            "- name: Set up Python", 1
        )[0]
        self.assertRegex(
            step,
            r"(?m)^\s+EXPECTED_HEAD_SHA:\s*\$\{\{\s*github\.event\.pull_request\.head\.sha\s*\|\|\s*github\.sha\s*\}\}\s*$",
        )
        self.assertIn('test "$actual" = "$EXPECTED_HEAD_SHA"', step)
        self.assertNotIn('test "$actual" = "$GITHUB_SHA"', step)

    def test_safety_flags_and_existing_trigger_scope_preserved(self):
        self.assertIn("pull_request:", self.text)
        self.assertIn("branches: [main, feat/cloud-paper-runner]", self.text)
        self.assertIn("'fix/cloud-paper-*'", self.text)
        for flag in ("PAPER_MODE: '1'", "LIVE_ORDER_AUTHORITY: '0'",
                     "REAL_BROKER_ORDERS: '0'"):
            self.assertIn(flag, self.text)


if __name__ == "__main__":
    unittest.main()
