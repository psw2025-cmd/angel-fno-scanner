"""Fail closed when PR Tests gains unreviewed steps or execution-context overrides.

This is a source regression guard, not authenticated CI or runtime evidence.
"""
from pathlib import Path
import re

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr_tests.yml"
EXPECTED_STEPS = (
    "      - uses: actions/checkout@v5",
    "      - uses: actions/setup-python@v6",
    "      - run: pip install -r requirements.txt -r relay/requirements.txt pytest",
    "      - run: python tools/memory_guard.py",
    "      - run: python tools/chaos_inject.py",
    "      - run: python -m pytest -q",
)


def assert_reviewed_step_inventory(source):
    """Reject extra/renamed steps that can mutate GITHUB_ENV before pytest."""
    assert re.search(r"(?m)^  pytest:\s*$", source), "Required pytest job missing"
    observed = tuple(line for line in source.splitlines() if line.startswith("      - "))
    assert observed == EXPECTED_STEPS, "Unreviewed step inventory or order"
    # Environment and shell overrides can change the effective command without
    # changing its literal '- run:' source. They require explicit review.
    assert not re.search(r"(?m)^ {4}(?:env|defaults|strategy|container|services)\s*:", source), "Unreviewed job execution context"
    assert not re.search(r"(?m)^ {8}(?:env|shell|working-directory)\s*:", source), "Unreviewed step execution context"
    assert not re.search(r"(?m)^defaults\s*:", source), "Unreviewed workflow defaults"


def test_reviewed_ci_step_inventory():
    assert_reviewed_step_inventory(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize("injection", [
    '      - run: echo "PYTEST_ADDOPTS=-k smoke" >> "$GITHUB_ENV"',
    '      - run: echo "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" >> "$GITHUB_ENV"',
    '      - name: Hidden setup\n        run: echo "PYTEST_ADDOPTS=-k smoke" >> "$GITHUB_ENV"',
    '      - uses: malicious/action@v1',
])
def test_extra_unreviewed_step_is_rejected(injection):
    source = WORKFLOW.read_text(encoding="utf-8")
    modified = source.replace("      - run: python -m pytest -q", injection + "\n      - run: python -m pytest -q", 1)
    assert modified != source
    with pytest.raises(AssertionError, match="Unreviewed step inventory"):
        assert_reviewed_step_inventory(modified)


@pytest.mark.parametrize("anchor,injection", [
    ("    timeout-minutes: 15", "    env:\n      PYTEST_ADDOPTS: '-k smoke'"),
    ("    timeout-minutes: 15", "    strategy:\n      matrix:\n        test: [smoke]"),
    ("      - run: python -m pytest -q", "        env:\n          PYTEST_ADDOPTS: '-k smoke'"),
    ("      - run: python -m pytest -q", "        shell: bash -e {0}"),
])
def test_unreviewed_execution_context_is_rejected(anchor, injection):
    source = WORKFLOW.read_text(encoding="utf-8")
    assert source.count(anchor) == 1
    modified = source.replace(anchor, anchor + "\n" + injection, 1)
    with pytest.raises(AssertionError, match="Unreviewed .* execution context"):
        assert_reviewed_step_inventory(modified)


def test_unreviewed_workflow_defaults_are_rejected():
    source = WORKFLOW.read_text(encoding="utf-8")
    modified = source.replace("jobs:\n", "defaults:\n  run:\n    shell: bash\njobs:\n", 1)
    with pytest.raises(AssertionError, match="Unreviewed workflow defaults"):
        assert_reviewed_step_inventory(modified)
