"""CDX-04 regression: image carries no .git and provenance resolves without git."""
from pathlib import Path

import pytest

from tools import cycle_provenance as cp

ROOT = Path(__file__).resolve().parents[1]


def _lines(name):
    return [ln.strip() for ln in (ROOT / name).read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("name", ["Dockerfile.cloudrun", "Dockerfile"])
def test_dockerfile_does_not_copy_git_history(name):
    # .git is in .dockerignore, so any `COPY .git` would also fail the build.
    assert not any(ln.startswith("COPY .git") for ln in _lines(name))


def test_dockerfile_bakes_source_commit_before_env():
    lines = _lines("Dockerfile.cloudrun")
    arg = lines.index("ARG SOURCE_COMMIT=unknown")
    assert lines.index("ENV GIT_SHA=$SOURCE_COMMIT") > arg
    assert any("/app/SOURCE_COMMIT" in ln for ln in lines)


def test_dockerignore_excludes_git_and_github():
    entries = set(_lines(".dockerignore"))
    assert ".git" in entries and ".github" in entries


@pytest.fixture
def clean_env(monkeypatch):
    for key in ("GITHUB_SHA", "GIT_SHA", "SOURCE_COMMIT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(cp, "_source_commit_files", lambda: [])


def test_git_sha_resolved_from_env_without_git(clean_env, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "a1b2c3d4e5")
    assert cp.resolve_git_sha() == "a1b2c3d4e5"


def test_git_sha_resolved_from_source_commit_file(clean_env, monkeypatch, tmp_path):
    f = tmp_path / "SOURCE_COMMIT"
    f.write_text("0e80b18b79f069df1c9813b1e210ef5472ee1a29\n", encoding="utf-8")
    monkeypatch.setattr(cp, "_source_commit_files", lambda: [f])
    assert cp.resolve_git_sha() == "0e80b18b79f069df1c9813b1e210ef5472ee1a29"


def test_unknown_build_arg_fails_closed(clean_env, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "unknown")
    with pytest.raises(RuntimeError, match="GIT_SHA missing or placeholder"):
        cp.resolve_git_sha()
