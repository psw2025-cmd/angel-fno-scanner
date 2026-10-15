"""Regression tests for Phase 0 findings (2026-10-15): integer policy, stale SHA, provenance, runtime budget."""
from pathlib import Path

import pytest

from tools import cycle_provenance as cp
from tools.live_schema_guard import SchemaGuardError, sanitize_bq_row
from tools.runtime_budget import effective_runtime_budget

ROOT = Path(__file__).resolve().parents[1]
GOOD_A = "a" * 40
GOOD_B = "b" * 40


# --- integer policy: never round fractional INT64 data -------------------------------------
@pytest.mark.parametrize("bad", [12.6, 2.5, 3.5, 0.1, -1.5, "7.25"])
def test_fractional_int64_is_refused_not_rounded(bad):
    with pytest.raises(SchemaGuardError):
        sanitize_bq_row("market_news_sentiment", {"source_count": bad})


@pytest.mark.parametrize("ok,expected", [(3.0, 3), (0.0, 0), ("4", 4), (-2.0, -2), (12, 12)])
def test_integral_values_still_accepted(ok, expected):
    out = sanitize_bq_row("market_news_sentiment", {"source_count": ok})
    assert out["source_count"] == expected and type(out["source_count"]) is int


def test_float_beyond_exact_integer_range_refused():
    with pytest.raises(SchemaGuardError):
        sanitize_bq_row("market_news_sentiment", {"source_count": 2.0 ** 60})


# --- stale-but-valid SHA must not silently override the baked commit ------------------------
@pytest.fixture
def clean_env(monkeypatch):
    for key in ("GITHUB_SHA", "GIT_SHA", "SOURCE_COMMIT"):
        monkeypatch.delenv(key, raising=False)


def _bake(monkeypatch, tmp_path, sha):
    f = tmp_path / "SOURCE_COMMIT"
    f.write_text(sha + "\n", encoding="utf-8")
    monkeypatch.setattr(cp, "_source_commit_files", lambda: [f])


def test_env_and_baked_sha_mismatch_fails_closed(clean_env, monkeypatch, tmp_path):
    _bake(monkeypatch, tmp_path, GOOD_A)
    monkeypatch.setenv("GIT_SHA", GOOD_B)
    with pytest.raises(RuntimeError, match="GIT_SHA mismatch"):
        cp.resolve_git_sha()


def test_matching_env_and_baked_sha_ok_and_short_prefix_ok(clean_env, monkeypatch, tmp_path):
    _bake(monkeypatch, tmp_path, GOOD_A)
    monkeypatch.setenv("GIT_SHA", GOOD_A)
    assert cp.resolve_git_sha() == GOOD_A
    monkeypatch.setenv("GIT_SHA", GOOD_A[:12])
    assert cp.resolve_git_sha() == GOOD_A


def test_placeholder_env_falls_back_to_baked_file(clean_env, monkeypatch, tmp_path):
    _bake(monkeypatch, tmp_path, GOOD_A)
    monkeypatch.setenv("GIT_SHA", "cloudrun-v2")  # current production job value
    assert cp.resolve_git_sha() == GOOD_A


def test_unknown_everywhere_fails_closed(clean_env, monkeypatch, tmp_path):
    _bake(monkeypatch, tmp_path, "unknown")
    monkeypatch.setenv("GIT_SHA", "unknown")
    with pytest.raises(RuntimeError, match="missing or placeholder"):
        cp.resolve_git_sha()


# --- both Dockerfiles bake provenance ------------------------------------------------------
@pytest.mark.parametrize("name", ["Dockerfile", "Dockerfile.cloudrun"])
def test_every_dockerfile_bakes_source_commit(name):
    lines = [ln.strip() for ln in (ROOT / name).read_text(encoding="utf-8").splitlines()]
    assert "ARG SOURCE_COMMIT=unknown" in lines
    assert lines.index("ENV GIT_SHA=$SOURCE_COMMIT") > lines.index("ARG SOURCE_COMMIT=unknown")
    assert any("/app/SOURCE_COMMIT" in ln for ln in lines)


# --- application budget must be shorter than the platform timeout --------------------------
def test_budget_clamped_below_platform_timeout_on_cloud_run():
    env = {"CLOUD_RUN_JOB": "angel-market-scan-job", "MAX_RUNTIME_SECONDS": "24300"}  # prod value today
    assert effective_runtime_budget(env) == 14400 - 600
    assert effective_runtime_budget(env) < 14400


def test_budget_respects_explicit_platform_timeout():
    env = {"CLOUD_RUN_JOB": "j", "MAX_RUNTIME_SECONDS": "24300", "PLATFORM_TIMEOUT_SECONDS": "7200"}
    assert effective_runtime_budget(env) == 6600


def test_budget_unchanged_when_already_shorter_or_not_on_cloud_run():
    assert effective_runtime_budget({"CLOUD_RUN_JOB": "j", "MAX_RUNTIME_SECONDS": "3000"}) == 3000
    assert effective_runtime_budget({"MAX_RUNTIME_SECONDS": "24300"}) == 24300
    assert effective_runtime_budget({}) == 22500
