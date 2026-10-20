"""Execute the real workflow shell with isolated command substitutes."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/market_bot.yml'


def run_publication(tmp_path, mode):
    git_bash = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/bin/bash.exe'
    bash = str(git_bash) if os.name == 'nt' and git_bash.is_file() else shutil.which('bash')
    if not bash:
        pytest.skip('Bash required for workflow shell behavior')
    text = WORKFLOW.read_text(encoding='utf-8')
    step = text.split('- name: Commit & Push Updated Snapshots', 1)[1]
    step = step.split('- name: Create Issue on Failure', 1)[0]
    source = step.split('run: |', 1)[1]
    # Remove the YAML block's base indentation without interpreting its commands.
    lines = source.splitlines()
    indent = min(len(line) - len(line.lstrip()) for line in lines if line.strip())
    source = '\n'.join(line[indent:] for line in lines)
    prefix = r'''
git() {
  printf 'GIT %s\n' "$*"
  case "$1" in
    diff-index) return 1 ;;
    fetch) [ "$CASE" != fetch_failure ] ;;
    rebase) [ "$CASE" != rebase_failure ] ;;
    push) [ "$CASE" != push_failure ] ;;
    *) return 0 ;;
  esac
}
gh() { printf 'GH %s\n' "$*"; [ "$CASE" != pr_failure ]; }
sleep() { :; }
'''
    env = dict(os.environ, CASE=mode, GITHUB_RUN_ID='test-run', PAPER_MODE='1', LIVE_ORDER_AUTHORITY='0')
    return subprocess.run([bash, '--noprofile', '--norc'], input=prefix + source,
                          cwd=tmp_path, env=env, capture_output=True, text=True, timeout=15)


@pytest.mark.parametrize('mode', ['fetch_failure', 'rebase_failure', 'push_failure'])
def test_failed_publication_never_opens_pr(tmp_path, mode):
    result = run_publication(tmp_path, mode)
    assert result.returncode != 0, result.stdout + result.stderr
    assert 'GH pr create' not in result.stdout
    if mode == 'push_failure':
        assert result.stdout.count('GIT push') == 5
    assert '--force' not in result.stdout


def test_success_push_opens_one_pr(tmp_path):
    result = run_publication(tmp_path, 'success')
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count('GIT push') == 1
    assert result.stdout.count('GH pr create') == 1
    assert result.stdout.index('GIT push') < result.stdout.index('GH pr create')
    assert '--force' not in result.stdout


def test_pr_creation_failure_propagates(tmp_path):
    result = run_publication(tmp_path, 'pr_failure')
    assert result.returncode != 0, result.stdout + result.stderr
    assert result.stdout.count('GH pr create') == 1
