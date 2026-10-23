"""Guard the exact-main-SHA PR Tests workflow contract without extra dependencies."""
from pathlib import Path
import re

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/pr_tests.yml'


def _workflow():
    return WORKFLOW.read_text(encoding='utf-8')


def test_main_push_and_pull_request_triggers_present():
    source = _workflow()
    assert re.search(r'(?m)^on:\s*$', source)
    assert re.search(r'(?m)^  push:\s*\n    branches:\s*\[main(?:,\s*[A-Za-z0-9_./*-]+)*\]\s*$', source)
    assert re.search(r'(?m)^  pull_request:\s*\n    branches:\s*\[main\]\s*$', source)
    assert re.search(r'(?m)^  workflow_dispatch:\s*$', source)


def test_full_pytest_memory_and_chaos_gates_preserved():
    source = _workflow()
    for command in ('python -m pytest -q', 'python tools/memory_guard.py', 'python tools/chaos_inject.py'):
        assert source.count('- run: ' + command) == 1


def test_mandatory_pytest_job_is_not_conditionally_skipped():
    source = _workflow()
    assert re.search(r'(?m)^  pytest:\s*$', source)
    assert not re.search(r'(?m)^  pytest:\s*\n\s+if:', source)
    assert not re.search(r'(?m)^      - if:', source)


def test_fail_closed_runner_budget_and_python_version():
    source = _workflow()
    assert 'timeout-minutes: 15' in source
    assert "python-version: '3.11'" in source
    assert 'cancel-in-progress: true' in source
def test_main_push_regex_does_not_accept_replacing_main_with_other():
    pattern = r'(?m)^  push:\s*\n    branches:\s*\[main(?:,\s*[A-Za-z0-9_./*-]+)*\]\s*$'
    assert re.search(pattern, "on:\n  push:\n    branches: [main]\n")
    assert re.search(pattern, "on:\n  push:\n    branches: [main, fix/ci-evidence-contract-regression-20261023]\n")
    assert not re.search(pattern, "on:\n  push:\n    branches: [other]\n")
