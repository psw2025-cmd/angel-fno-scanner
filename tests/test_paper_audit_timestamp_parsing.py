"""Regression: C08 compares chronological timestamps, not lexical representations."""
import ast
import datetime
from pathlib import Path


def _extract_parser():
    source = Path(__file__).resolve().parents[1] / 'tools' / 'forensic_paper_sheet_audit.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    fn = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'parse_paper_time')
    module = ast.Module(body=[fn], type_ignores=[])
    import re
    ns = {'datetime': datetime, 're': re}
    exec(compile(ast.fix_missing_locations(module), str(source), 'exec'), ns)
    return ns['parse_paper_time']


def test_gviz_date_month_is_zero_based():
    parse = _extract_parser()
    assert parse('Date(2026,9,7,9,19,24)') == datetime.datetime(2026,10,7,9,19,24)


def test_gviz_entry_is_before_iso_exit():
    parse = _extract_parser()
    assert parse('Date(2026,9,7,9,19,24)') < parse('2026-10-08 12:51:51')


def test_invalid_timestamp_fails_closed():
    parse = _extract_parser()
    assert parse('not a timestamp') is None
    assert parse('') is None
