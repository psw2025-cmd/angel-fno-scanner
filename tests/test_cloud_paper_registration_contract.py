"""Mutations that fooled the previous string-search registration safety tests."""
from pathlib import Path

import pytest

from tools.cloud_paper_registration_contract import validate, verify_execution

SOURCE = (Path(__file__).resolve().parents[1] / '.github/workflows/cloud-paper-runner.yml').read_text(encoding='utf-8')


def test_real_registration_shell_exits_nonzero_without_orders():
    verify_execution(SOURCE)


@pytest.mark.parametrize('old,new', [
    ('on: workflow_dispatch', 'on: [workflow_dispatch, push]'),
    ("REAL_BROKER_ORDERS: '0'", "REAL_BROKER_ORDERS: '1'"),
    ('exit 1', 'exit 0'),
    ('exit 1', 'echo "Registered"\n          exit 1'),
    ('no broker feed,', 'no broker $(id) feed,'),
])
def test_semantic_guard_rejects_mutations_that_string_checks_missed(old, new):
    assert old in SOURCE
    with pytest.raises(ValueError):
        validate(SOURCE.replace(old, new, 1))
