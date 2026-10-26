"""Fail-closed checks for authenticated PR audit workflow token isolation.

No external YAML dependency: reject unsafe workflow source mutations rather
than treating the presence of isolated safe-looking strings as certification.
"""
import re
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr-dependency-audit.yml"


def validate_workflow_security(workflow):
    active = "\n".join(
        line for line in workflow.splitlines()
        if not line.lstrip().startswith("#")
    )
    if re.search(r"(?m)^\s*pull_request(?:_target)?\s*:", active):
        raise AssertionError("untrusted pull_request trigger")
    if "github.event.pull_request" in active:
        raise AssertionError("untrusted PR checkout expression")
    if not re.search(r"(?m)^\s+push:\s*$", active):
        raise AssertionError("owned direct-head push trigger missing")

    checkout_markers = re.findall(
        r"(?m)^\s*-\s+uses:\s+actions/checkout@", active
    )
    if len(checkout_markers) != 1:
        raise AssertionError("exactly one checkout step required")
    checkout_start = "      - uses: actions/checkout@v4\n"
    if active.count(checkout_start) != 1:
        raise AssertionError("checkout version/indentation changed")
    checkout_step = active.split(checkout_start, 1)[1].split(
        "\n      - ", 1
    )[0]
    for expected in (
        "          repository: ${{ github.repository }}",
        "          ref: ${{ github.sha }}",
        "          persist-credentials: false",
    ):
        if expected not in checkout_step:
            raise AssertionError("checkout identity or credential isolation missing")

    inventory_marker = "      - name: Authenticated read-only PR dependency inventory"
    preserve_marker = "      - name: Preserve audit snapshot"
    before, sep, after = active.partition(inventory_marker)
    if not sep:
        raise AssertionError("authenticated inventory step missing")
    inventory_step, sep, following = after.partition(preserve_marker)
    if not sep:
        raise AssertionError("evidence preservation step missing")
    token_declarations = re.findall(
        r"(?m)^\s*GITHUB_TOKEN\s*:\s*(.+?)\s*$", active
    )
    if token_declarations != ["${{ github.token }}"]:
        raise AssertionError("token must have exactly one trusted declaration")
    if "GITHUB_TOKEN:" in before or "GITHUB_TOKEN:" in following:
        raise AssertionError("token declared outside inventory step")
    if "          GITHUB_TOKEN: ${{ github.token }}" not in inventory_step:
        raise AssertionError("token not scoped to inventory step")
    if "python tools/pr_dependency_audit.py" not in inventory_step:
        raise AssertionError("authenticated inventory command missing")

    preserve_step = following.split("\n      - ", 1)[0]
    for expected in (
        "        if: always()",
        "        uses: actions/upload-artifact@v4",
        "          path: proof-output/pr-dependency/inventory.json",
        "          if-no-files-found: error",
    ):
        if expected not in preserve_step:
            raise AssertionError("audit artifact fail-closed contract missing")

    job_before_steps = active.partition("    steps:")[0]
    if "EXPECTED_HEAD_SHA: ${{ github.sha }}" not in active:
        raise AssertionError("exact-head verification missing")
    for flag in (
        "PAPER_MODE: '1'",
        "LIVE_ORDER_AUTHORITY: '0'",
        "REAL_BROKER_ORDERS: '0'",
    ):
        if flag not in job_before_steps:
            raise AssertionError("PAPER/no-order job safety flag missing")


class AuditTokenScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_no_untrusted_pull_request_trigger(self):
        validate_workflow_security(self.workflow)

    def test_checkout_does_not_persist_credentials(self):
        validate_workflow_security(self.workflow)

    def test_token_only_in_inventory_step(self):
        validate_workflow_security(self.workflow)

    def test_exact_sha_and_paper_flags_preserved(self):
        validate_workflow_security(self.workflow)

    def test_rejects_alternate_indent_pull_request_trigger(self):
        mutated = self.workflow.replace(
            "  workflow_dispatch:",
            " pull_request:\n  workflow_dispatch:", 1,
        )
        with self.assertRaisesRegex(AssertionError, "untrusted pull_request"):
            validate_workflow_security(mutated)

    def test_rejects_token_in_later_step(self):
        mutated = self.workflow.replace(
            "      - name: Preserve audit snapshot",
            "      - name: Unsafe later step\n"
            "        env:\n"
            "          GITHUB_TOKEN: ${{ github.token }}\n"
            "        run: echo unsafe\n"
            "      - name: Preserve audit snapshot", 1,
        )
        with self.assertRaisesRegex(AssertionError, "token must have exactly one"):
            validate_workflow_security(mutated)

    def test_rejects_second_checkout_step(self):
        mutated = self.workflow.replace(
            "      - name: Preserve audit snapshot",
            "      - uses: actions/checkout@v4\n"
            "      - name: Preserve audit snapshot", 1,
        )
        with self.assertRaisesRegex(AssertionError, "exactly one checkout"):
            validate_workflow_security(mutated)

    def test_rejects_removed_credential_isolation(self):
        mutated = self.workflow.replace(
            "          persist-credentials: false\n", "", 1,
        )
        with self.assertRaisesRegex(AssertionError, "credential isolation"):
            validate_workflow_security(mutated)


    def test_rejects_missing_artifact_fail_closed(self):
        mutated = self.workflow.replace(
            "          if-no-files-found: error",
            "          if-no-files-found: warn", 1,
        )
        with self.assertRaisesRegex(AssertionError, "audit artifact fail-closed"):
            validate_workflow_security(mutated)

    def test_rejects_wrong_artifact_path(self):
        mutated = self.workflow.replace(
            "          path: proof-output/pr-dependency/inventory.json",
            "          path: proof-output/pr-dependency/unknown.json", 1,
        )
        with self.assertRaisesRegex(AssertionError, "audit artifact fail-closed"):
            validate_workflow_security(mutated)


if __name__ == "__main__":
    unittest.main()
