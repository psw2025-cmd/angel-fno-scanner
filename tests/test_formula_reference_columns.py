"""Check real reference validator without importing network-owning modules."""
import ast
from pathlib import Path
import re

import pytest


def check_reference(formula, values):
    source = Path(__file__).resolve().parents[1] / 'tools/verify_harness.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    function = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == 'check_gate_formulas')
    namespace = {'re': re}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
    # Missing mandatory gates deliberately stay FAIL; isolate only the reference finding.
    return namespace['check_gate_formulas']([['EXTRA', '', formula]], {'Data': values}, None)[2]


@pytest.mark.parametrize('formula,values,expected', [
    ('=Data!B1', [['unrelated', '']], 'Data!B1'),
    ('=Data!AA1', [['unrelated'] + [''] * 25 + ['']], 'Data!AA1'),
    ('=Data!B2:C3', [['header'], ['unrelated'], ['also unrelated']], 'Data!B2:C3'),
])
def test_unrelated_columns_do_not_satisfy_reference(formula, values, expected):
    assert expected in check_reference(formula, values)


@pytest.mark.parametrize('formula,values', [
    ('=Data!B1', [['', 'present']]),
    ('=Data!AA1', [[''] * 26 + ['present']]),
    ('=Data!B2:C3', [[], ['', '', 'present']]),
    ('=Data!B1', [['', 0]]),
])
def test_value_inside_reference_is_detected(formula, values):
    assert not any(issue.startswith('Data!') for issue in check_reference(formula, values))
