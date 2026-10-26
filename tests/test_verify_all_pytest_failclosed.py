"""Offline negative regressions for the unified verifier's pytest verdict.

The production function is extracted via AST to avoid loading live broker or
BigQuery dependencies. These tests do NOT establish external integration proof.
"""
import ast
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "verify_all.py"


def _run_verifier(stdout, *, exit_code=0):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "check_pytest")
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return SimpleNamespace(returncode=exit_code, stdout=stdout, stderr="")

    scope = {
        "subprocess": SimpleNamespace(run=fake_run),
        "sys": sys,
        "REPO_ROOT": ROOT,
        "re": re,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), scope)
    result = scope["check_pytest"]()
    assert calls and calls[0][:3] == [sys.executable, "-m", "pytest"]
    return result


def test_clean_non_skipped_pytest_can_pass():
    result = _run_verifier("2 passed in 0.11s\n")
    assert result["status"] == "PASS"
    assert result["passed_count"] == 2
    assert result["skipped_count"] == 0


def test_skipped_integration_is_not_certified_by_exit_zero():
    result = _run_verifier("372 passed, 3 skipped, 3 warnings in 20.55s\n")
    assert result["status"] == "FAIL"
    assert result["skipped_count"] == 3


def test_skips_without_passes_are_not_certified():
    result = _run_verifier("3 skipped in 0.10s\n")
    assert result["status"] == "FAIL"
    assert result["passed_count"] == 0
    assert result["skipped_count"] == 3


def test_empty_or_unparseable_summary_fails_closed():
    for output in ("", "all tests passed\n", "no tests ran in 0.01s\n"):
        result = _run_verifier(output)
        assert result["status"] == "FAIL", output


def test_nonzero_exit_fails_even_if_summary_says_pass():
    result = _run_verifier("2 passed in 0.11s\n", exit_code=2)
    assert result["status"] == "FAIL"


def test_explicit_zero_skips_remains_valid():
    result = _run_verifier("2 passed, 0 skipped in 0.11s\n")
    assert result["status"] == "PASS"
    assert result["skipped_count"] == 0
