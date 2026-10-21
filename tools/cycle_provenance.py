"""Resolve publication identity from the execution and the source commit.

Static placeholders such as ``cloudrun-scheduled`` and ``cloudrun-image-v1``
are rejected. This module never invents a git SHA.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

PLACEHOLDER_RUN_IDS = frozenset({
    "",
    "unset",
    "unknown",
    "none",
    "local",
    "test",
    "cloudrun-scheduled",
    "cloudrun-image-v1",
})
PLACEHOLDER_GIT_SHAS = frozenset({
    "",
    "unset",
    "unknown",
    "none",
    "head",
    "local",
    "cloudrun-image-v1",
    "cloudrun-scheduled",
})
_GIT_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def is_real_git_sha(value: str | None) -> bool:
    text = (value or "").strip().lower()
    if text in PLACEHOLDER_GIT_SHAS:
        return False
    return _GIT_SHA.fullmatch(text) is not None


def _usable_run_id(value: str | None) -> str:
    text = (value or "").strip()
    if text.lower() in PLACEHOLDER_RUN_IDS:
        return ""
    return text


def resolve_run_id() -> str:
    """Prefer the Cloud Run execution id when RUN_ID is a static placeholder."""
    cloud = _usable_run_id(os.getenv("CLOUD_RUN_EXECUTION"))
    github = _usable_run_id(os.getenv("GITHUB_RUN_ID"))
    explicit = _usable_run_id(os.getenv("RUN_ID"))
    chosen = cloud or github or explicit
    if not chosen:
        raise RuntimeError(
            "RUN_ID missing or placeholder; refusing to invent an execution id"
        )
    return chosen


def _source_commit_files() -> list[Path]:
    repo_file = Path(__file__).resolve().parents[1] / "SOURCE_COMMIT"
    return [Path("/app/SOURCE_COMMIT"), repo_file]


def resolve_git_sha() -> str:
    """Return a real source commit. Never substitute a tag or a fake SHA.

    Fails closed when a valid env SHA and a valid baked SOURCE_COMMIT file disagree
    (a stale-but-valid env value must not silently override the image's real commit).
    """
    env_sha = ""
    for key in ("GITHUB_SHA", "GIT_SHA", "SOURCE_COMMIT"):
        candidate = (os.getenv(key) or "").strip().lower()
        if is_real_git_sha(candidate):
            env_sha = candidate
            break
    file_sha = ""
    for path in _source_commit_files():
        try:
            if path.is_file():
                candidate = path.read_text(encoding="utf-8").strip().splitlines()[0].strip().lower()
                if is_real_git_sha(candidate):
                    file_sha = candidate
                    break
        except OSError:
            continue
    if env_sha and file_sha:
        if not (env_sha.startswith(file_sha) or file_sha.startswith(env_sha)):
            raise RuntimeError(
                f"GIT_SHA mismatch: env={env_sha[:12]} baked SOURCE_COMMIT={file_sha[:12]}; refusing to publish"
            )
        return env_sha if len(env_sha) >= len(file_sha) else file_sha
    if env_sha:
        return env_sha
    if file_sha:
        return file_sha
    raise RuntimeError(
        "GIT_SHA missing or placeholder; refusing a fake SHA. "
        "Bake SOURCE_COMMIT from git rev-parse at image build."
    )


def apply_process_provenance() -> dict[str, str]:
    """Replace placeholder process env with derived identity for this process only."""
    run_id = resolve_run_id()
    git_sha = resolve_git_sha()
    os.environ["RUN_ID"] = run_id
    os.environ["GIT_SHA"] = git_sha
    return {"run_id": run_id, "git_sha": git_sha}
