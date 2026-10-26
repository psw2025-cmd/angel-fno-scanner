"""Fail-closed regression for GitHub PR audit token scope and checkout provenance."""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr-dependency-audit.yml"

class AuditTokenScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_no_untrusted_pull_request_trigger(self):
        self.assertNotRegex(self.workflow, r"(?m)^  pull_request(?:_target)?:")
        self.assertNotIn("github.event.pull_request", self.workflow)
        self.assertIn("  push:", self.workflow)

    def test_checkout_does_not_persist_credentials(self):
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("repository: ${{ github.repository }}", self.workflow)
        self.assertIn("ref: ${{ github.sha }}", self.workflow)

    def test_token_only_in_inventory_step(self):
        prefix, sep, inventory = self.workflow.partition(
            "      - name: Authenticated read-only PR dependency inventory"
        )
        self.assertTrue(sep, "authenticated inventory step is mandatory")
        self.assertNotIn("GITHUB_TOKEN:", prefix)
        step, sep2, _ = inventory.partition("      - name: Preserve audit snapshot")
        self.assertTrue(sep2, "evidence preservation step is mandatory")
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", step)
        self.assertIn("python tools/pr_dependency_audit.py", step)

    def test_exact_sha_and_paper_flags_preserved(self):
        self.assertIn("EXPECTED_HEAD_SHA: ${{ github.sha }}", self.workflow)
        for flag in ("PAPER_MODE: '1'", "LIVE_ORDER_AUTHORITY: '0'",
                     "REAL_BROKER_ORDERS: '0'"):
            self.assertIn(flag, self.workflow)

if __name__ == "__main__":
    unittest.main()
