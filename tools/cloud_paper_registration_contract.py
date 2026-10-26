"""Validate and safely exercise the registration-only Cloud PAPER workflow.

This is a negative readiness control, not proof of a deployed PAPER runner.
"""
import re
import subprocess
import tempfile
from pathlib import Path

import yaml

class _UniqueKeyBaseLoader(yaml.BaseLoader):
    """Reject duplicate YAML mapping keys instead of silently taking the last."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            if not isinstance(key_node, yaml.ScalarNode):
                raise ValueError('unsupported non-scalar YAML mapping key')
            key = key_node.value
            if key in seen:
                raise ValueError(f'duplicate YAML mapping key: {key}')
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/cloud-paper-runner.yml'
FLAGS = {'PAPER_MODE': '1', 'LIVE_ORDER_AUTHORITY': '0', 'REAL_BROKER_ORDERS': '0'}
_ECHO = re.compile(r'echo "::error::CLOUD_PAPER_NOT_DEPLOYED: [A-Za-z0-9 ,.;:\-]+" >&2\Z')


def validate(source: str) -> str:
    """Return the bounded fail-closed shell script or reject the YAML."""
    try:
        doc = yaml.load(source, Loader=_UniqueKeyBaseLoader)
    except yaml.YAMLError as exc:
        raise ValueError('invalid workflow YAML') from exc
    if not isinstance(doc, dict) or set(doc) != {'name', 'on', 'permissions', 'jobs'} or doc.get('on') != 'workflow_dispatch':
        raise ValueError('registration workflow must be manual only')
    if doc.get('permissions') != {'contents': 'read'}:
        raise ValueError('registration permissions must be read-only')
    jobs = doc.get('jobs')
    if not isinstance(jobs, dict) or set(jobs) != {'registration-only'}:
        raise ValueError('unexpected registration jobs')
    job = jobs['registration-only']
    if not isinstance(job, dict) or set(job) != {'runs-on', 'timeout-minutes', 'env', 'steps'} or job.get('env') != FLAGS:
        raise ValueError('unsafe PAPER flags')
    if job.get('runs-on') != 'ubuntu-latest' or job.get('timeout-minutes') != '2':
        raise ValueError('unexpected registration runtime')
    steps = job.get('steps')
    if not isinstance(steps, list) or len(steps) != 1 or not isinstance(steps[0], dict):
        raise ValueError('registration must have exactly one fail-closed step')
    step = steps[0]
    if step.get('shell') != 'bash' or set(step) != {'name', 'shell', 'run'}:
        raise ValueError('unexpected registration step configuration')
    script = step.get('run')
    if not isinstance(script, str):
        raise ValueError('missing registration script')
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    if len(lines) != 2 or not _ECHO.fullmatch(lines[0]) or lines[1] != 'exit 1':
        raise ValueError('registration script is not a bounded fail-closed marker')
    return '\n'.join(lines)


def verify_execution(source: str) -> None:
    """Execute only the statically bounded marker script in a temporary directory."""
    script = validate(source)
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-c', script],
            cwd=directory, env={'PATH': '/usr/bin:/bin'},
            capture_output=True, text=True, timeout=5, check=False,
        )
    if result.returncode != 1 or 'CLOUD_PAPER_NOT_DEPLOYED:' not in result.stderr or result.stdout:
        raise ValueError('registration dispatch did not fail closed')
