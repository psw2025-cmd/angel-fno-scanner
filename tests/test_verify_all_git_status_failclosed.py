"""Offline regressions: unified verifier must not certify an unsafe git checkout.

The production main() function is extracted by AST. No broker, BigQuery,
Sheets, cloud or order APIs are invoked. This is not production proof.
"""
import ast
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "verify_all.py"


def _run_main(tmp_path, git_status):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "main")
    scope = {
        "datetime": datetime,
        "IST": datetime.timezone.utc,
        "REPO_ROOT": tmp_path,
        "json": json,
        "check_git": lambda: {"status": git_status},
        "check_pytest": lambda: {"status": "PASS", "passed_count": 2,
                                 "skipped_count": 0, "exit_code": 0},
        "check_bigquery_types": lambda: {"status": "PASS"},
        "check_formula_contract": lambda: {"status": "PASS"},
        "run_readiness_probe": lambda: {
            "status": "PASS", "fail_count": 0, "other_count": 0,
            "checks": {"independent_probe": "PASS"},
        },
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]),
                 str(SOURCE), "exec"), scope)
    exit_code = scope["main"]()
    report = json.loads((tmp_path / "audit" / "verify_report.json").read_text())
    return exit_code, report


def test_clean_synchronized_git_can_pass_otherwise_clean_verification(tmp_path):
    exit_code, report = _run_main(tmp_path, "PASS")
    assert exit_code == 0
    assert report["overall_status"] == "PASS"


def test_dirty_checkout_cannot_certify_full_verification(tmp_path):
    exit_code, report = _run_main(tmp_path, "WARN_DIRTY")
    assert exit_code == 1
    assert report["overall_status"] == "FAIL"
    assert any("Git" in x for x in report["critical_failures"])


def test_diverged_checkout_cannot_certify_full_verification(tmp_path):
    exit_code, report = _run_main(tmp_path, "WARN_DIVERGED")
    assert exit_code == 1
    assert report["overall_status"] == "FAIL"
    assert any("Git" in x for x in report["critical_failures"])


def test_unrecognized_git_status_fails_closed(tmp_path):
    exit_code, report = _run_main(tmp_path, "UNKNOWN")
    assert exit_code == 1
    assert report["overall_status"] == "FAIL"
