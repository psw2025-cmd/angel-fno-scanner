"""Prevent a green PR Tests job from hiding a disabled or tolerated required gate.

This is a static workflow regression guard, not proof that GitHub ran the tests.
It deliberately fails closed when mandatory step YAML changes shape and needs review.
"""
from pathlib import Path
import re

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/pr_tests.yml"
REQUIRED = (
    "python tools/memory_guard.py",
    "python tools/chaos_inject.py",
    "python -m pytest -q",
)


def assert_required_steps_fail_closed(source):
    # Even if GitHub reports a green job, continue-on-error can mask failures.
    assert not re.search(r"(?m)^\s*continue-on-error\s*:", source), "CI failure tolerance is forbidden"
    assert re.search(r"(?m)^  pytest:\s*$", source), "Required pytest job missing"
    # A job-level if may appear after runs-on, timeout, or other keys.
    # Scope the check to the mandatory job, not unrelated future jobs.
    job_header = re.search(r"(?m)^  pytest: *$", source)
    assert job_header, "Required pytest job missing"
    job_tail = source[job_header.end():]
    next_job = re.search(r"(?m)^  [A-Za-z_][A-Za-z0-9_-]*: *$", job_tail)
    job_body = job_tail[:next_job.start()] if next_job else job_tail
    assert not re.search(r"(?m)^    if *:", job_body), "Required job is conditional"
    lines = source.splitlines()
    for command in REQUIRED:
        marker = "      - run: " + command
        indices = [i for i, line in enumerate(lines) if line == marker]
        assert len(indices) == 1, "Required command missing, changed or duplicated: " + command
        i = indices[0] + 1
        while i < len(lines):
            line = lines[i]
            if line.strip() and (len(line) - len(line.lstrip()) <= 6):
                break
            assert not re.match(r"\s*if\s*:", line), "Required step is conditional: " + command
            i += 1


def test_current_required_ci_steps_are_unconditional_and_fail_closed():
    assert_required_steps_fail_closed(WORKFLOW.read_text(encoding="utf-8"))


@pytest.mark.parametrize("injected", [
    "        continue-on-error: true",
    "        continue-on-error: ${{ always() }}",
    "        if: false",
    "        if: ${{ github.ref == 'refs/heads/never' }}",
])
def test_required_pytest_step_cannot_be_disabled_or_tolerated(injected):
    source = WORKFLOW.read_text(encoding="utf-8")
    source = source.replace("      - run: python -m pytest -q", "      - run: python -m pytest -q\n" + injected, 1)
    with pytest.raises(AssertionError):
        assert_required_steps_fail_closed(source)


def test_required_job_cannot_be_conditionally_skipped():
    source = WORKFLOW.read_text(encoding="utf-8")
    source = source.replace("  pytest:\n", "  pytest:\n    if: false\n", 1)
    with pytest.raises(AssertionError):
        assert_required_steps_fail_closed(source)


def test_required_command_cannot_be_masked_by_shell_fallback():
    source = WORKFLOW.read_text(encoding="utf-8")
    source = source.replace("      - run: python -m pytest -q", "      - run: python -m pytest -q || true", 1)
    with pytest.raises(AssertionError):
        assert_required_steps_fail_closed(source)


@pytest.mark.parametrize("anchor,injected", [
    ("    runs-on: ubuntu-latest", "    if: false"),
    ("    timeout-minutes: 15", "    if: ${{ false }}"),
    ("    timeout-minutes: 15", "    if : >-\n      false"),
])
def test_required_job_if_after_other_keys_is_rejected(anchor, injected):
    """Job-level if anywhere in pytest job must fail, not only first line."""
    source = WORKFLOW.read_text(encoding="utf-8")
    assert source.count(anchor) == 1
    modified = source.replace(anchor, anchor + "\n" + injected, 1)
    with pytest.raises(AssertionError, match="Required job is conditional"):
        assert_required_steps_fail_closed(modified)
