"""Offline negative regressions for freshly queried GitHub origin/main identity.

Only the check_git AST function executes; git/network are monkeypatched.
These are structural/behavioral unit tests, NOT authenticated deployment proof.
"""
import ast
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "verify_all.py"
SHA_A = "a" * 40
SHA_B = "b" * 40


def _check(monkeypatch, *, porcelain="", local=SHA_A, remote=SHA_A,
           remote_exit=0, remote_text=None, remote_error=None,
           local_error=None, remote_url="https://github.com/psw2025-cmd/angel-fno-scanner.git"):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "check_git")
    calls = []

    def check_output(argv, **kwargs):
        calls.append(tuple(argv))
        if local_error is not None:
            raise local_error
        if argv == ["git", "status", "--porcelain"]:
            return porcelain
        if argv == ["git", "rev-parse", "HEAD"]:
            return local + "\n"
        if argv == ["git", "remote", "get-url", "origin"]:
            return remote_url + "\n"
        raise AssertionError("Unexpected or stale local git ref: " + repr(argv))

    def run(argv, **kwargs):
        calls.append(tuple(argv))
        assert argv == ["git", "ls-remote", "--exit-code",
                        "origin", "refs/heads/main"]
        assert kwargs.get("capture_output") is True
        assert kwargs.get("text") is True
        assert 0 < kwargs.get("timeout", 0) <= 30
        if remote_error is not None:
            raise remote_error
        output = remote_text if remote_text is not None else (
            remote + "\trefs/heads/main\n")
        return SimpleNamespace(returncode=remote_exit, stdout=output,
                               stderr="private stderr must never be logged")

    monkeypatch.setattr(subprocess, "check_output", check_output)
    monkeypatch.setattr(subprocess, "run", run)
    scope = {"subprocess": subprocess, "REPO_ROOT": SOURCE.parent.parent,
             "re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]),
                 str(SOURCE), "exec"), scope)
    result = scope["check_git"]()
    return result, calls


def test_fresh_remote_sha_required_and_tracking_ref_not_trusted(monkeypatch):
    result, calls = _check(monkeypatch)
    assert result["status"] == "PASS"
    assert result["remote_sha"] == SHA_A
    assert result["remote_verified"] is True
    assert ("git", "rev-parse", "origin/main") not in calls
    assert ("git", "ls-remote", "--exit-code",
            "origin", "refs/heads/main") in calls


def test_stale_tracking_ref_cannot_hide_fresh_remote_divergence(monkeypatch):
    result, _ = _check(monkeypatch, remote=SHA_B)
    assert result["status"] == "WARN_DIVERGED"
    assert result["is_synced"] is False


def test_remote_auth_or_network_failure_blocks_verification(monkeypatch):
    result, _ = _check(monkeypatch, remote_exit=128)
    assert result["status"] == "BLOCKED_REMOTE"
    assert result["remote_verified"] is False
    assert result["is_synced"] is False


def test_remote_timeout_blocks_verification(monkeypatch):
    result, _ = _check(
        monkeypatch, remote_error=subprocess.TimeoutExpired(
            ["git", "ls-remote"], 15))
    assert result["status"] == "BLOCKED_REMOTE"


@pytest.mark.parametrize("raw", [
    "", "garbage", SHA_A + "\trefs/heads/develop\n",
    SHA_A + "\trefs/heads/main\n" + SHA_B + "\trefs/heads/main\n",
    "notasha\trefs/heads/main\n",
])
def test_invalid_or_ambiguous_remote_response_blocks(monkeypatch, raw):
    result, _ = _check(monkeypatch, remote_text=raw)
    assert result["status"] == "BLOCKED_REMOTE"
    assert result["remote_verified"] is False


def test_dirty_checkout_still_blocks_even_with_fresh_matching_sha(monkeypatch):
    result, _ = _check(monkeypatch, porcelain="?? untracked.txt\n")
    assert result["status"] == "WARN_DIRTY"


def test_local_git_command_error_is_reported_not_uncaught(monkeypatch):
    result, _ = _check(
        monkeypatch, local_error=subprocess.CalledProcessError(
            128, ["git", "status"]))
    assert result["status"] == "BLOCKED_LOCAL"
    assert result["remote_verified"] is False


@pytest.mark.parametrize("trusted_url", [
    "https://github.com/psw2025-cmd/angel-fno-scanner.git",
    "https://github.com/psw2025-cmd/angel-fno-scanner",
    "git@github.com:psw2025-cmd/angel-fno-scanner.git",
    "ssh://git@github.com/psw2025-cmd/angel-fno-scanner.git",
])
def test_trusted_origin_url_is_verified_before_remote_sha(monkeypatch, trusted_url):
    result, calls = _check(monkeypatch, remote_url=trusted_url)
    assert result["status"] == "PASS"
    assert ("git", "remote", "get-url", "origin") in calls
    assert calls.index(("git", "remote", "get-url", "origin")) < calls.index(
        ("git", "ls-remote", "--exit-code", "origin", "refs/heads/main"))


@pytest.mark.parametrize("untrusted_url", [
    "https://github.com/attacker/angel-fno-scanner.git",
    "https://github.com/psw2025-cmd/other-repo.git",
    "https://github.com.evil.example/psw2025-cmd/angel-fno-scanner.git",
    "https://user:secret@github.com/psw2025-cmd/angel-fno-scanner.git",
    "http://github.com/psw2025-cmd/angel-fno-scanner.git",
    "git@evil.example:psw2025-cmd/angel-fno-scanner.git",
    "../angel-fno-scanner",
    "",
])
def test_untrusted_origin_url_cannot_certify_matching_sha(monkeypatch, untrusted_url):
    result, calls = _check(monkeypatch, remote_url=untrusted_url)
    assert result["status"] == "BLOCKED_REMOTE"
    assert result["remote_verified"] is False
    assert result["is_synced"] is False
    assert ("git", "ls-remote", "--exit-code", "origin", "refs/heads/main") not in calls
    assert "secret" not in str(result)
