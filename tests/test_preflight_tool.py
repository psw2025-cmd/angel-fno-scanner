from tools.preflight import FAIL, NOT_PROVEN, PASS, evaluate

GOOD_SHA = "cc057b9cf4ebf0aed8b352d62e109b161fba649c"
COLS = ["symbol", "cycle_id", "data_freshness_status", "git_sha", "run_id", "source_timestamp", "writer_id"]


def _good():
    return {
        "git": {"head": GOOD_SHA, "remote_main": GOOD_SHA},
        "job": {
            "image": "r/scanner@sha256:" + "a" * 64,
            "timeout_seconds": 14400,
            "env": {"MAX_RUNTIME_SECONDS": "13800"},
            "executions": [],
        },
        "scheduler": {"a": "ENABLED"},
        "bigquery": {"columns": COLS, "n": 219, "syms": 219, "git_sha_nonnull": 219},
        "github_secrets": {"repo": ["ANGEL_API_KEY", "SHEET_ID"], "env": {"phase2-paper": []}},
        "sheet": {"gates": {"GATE-01": "PASS", "OVERALL": "PASS"}},
    }


def _by(checks):
    return {c["check"]: c["status"] for c in checks}


def test_all_good_has_no_fail_or_unproven():
    statuses = set(_by(evaluate(_good())).values())
    assert statuses == {PASS}


def test_missing_provenance_column_fails():
    ev = _good()
    ev["bigquery"]["columns"] = [c for c in COLS if c != "git_sha"]
    assert _by(evaluate(ev))["provenance_columns_present"] == FAIL


def test_partial_universe_fails():
    ev = _good()
    ev["bigquery"].update(n=200, syms=200)
    assert _by(evaluate(ev))["universe_complete"] == FAIL


def test_null_git_sha_rows_fail():
    ev = _good()
    ev["bigquery"]["git_sha_nonnull"] = 0
    assert _by(evaluate(ev))["rows_have_git_sha"] == FAIL


def test_budget_equal_to_timeout_fails():
    ev = _good()
    ev["job"]["env"]["MAX_RUNTIME_SECONDS"] = "14400"
    assert _by(evaluate(ev))["runtime_budget_below_platform_timeout"] == FAIL


def test_placeholder_git_sha_env_fails():
    ev = _good()
    ev["job"]["env"]["GIT_SHA"] = "cloudrun-v2"
    assert _by(evaluate(ev))["git_sha_env_not_placeholder"] == FAIL


def test_tag_only_image_fails():
    ev = _good()
    ev["job"]["image"] = "r/scanner:latest"
    assert _by(evaluate(ev))["job_image_digest_pinned"] == FAIL


def test_failing_sheet_gate_fails_and_is_named():
    ev = _good()
    ev["sheet"]["gates"]["GATE-04"] = "FAIL"
    checks = {c["check"]: c for c in evaluate(ev)}
    assert checks["sheet_gates"]["status"] == FAIL
    assert "GATE-04" in checks["sheet_gates"]["detail"]


def test_environment_secret_shadowing_repo_secret_fails():
    ev = _good()
    ev["github_secrets"]["env"] = {"phase2-paper": ["ANGEL_API_KEY"]}
    checks = {c["check"]: c for c in evaluate(ev)}
    assert checks["env_secrets_not_shadowing_repo"]["status"] == FAIL
    assert "ANGEL_API_KEY" in checks["env_secrets_not_shadowing_repo"]["detail"]


def test_environment_only_secret_names_do_not_fail():
    ev = _good()
    ev["github_secrets"]["env"] = {"phase2-paper": ["ONLY_IN_ENV"]}
    assert _by(evaluate(ev))["env_secrets_not_shadowing_repo"] == PASS


def test_unmeasurable_sources_are_not_proven_never_pass():
    ev = {"git": {}, "job": {"error": "x"}, "scheduler": {"error": "x"}, "bigquery": {"error": "x"},
          "github_secrets": {"error": "x"}, "sheet": {"error": "x"}}
    statuses = set(_by(evaluate(ev)).values())
    assert statuses == {NOT_PROVEN}
