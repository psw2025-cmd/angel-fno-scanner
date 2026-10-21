"""Provenance placeholders and the paper-cycle fencing decision."""
import datetime

import pytest

from tools.cycle_provenance import (
    apply_process_provenance,
    is_real_git_sha,
    resolve_git_sha,
    resolve_run_id,
)
from tools.publication_lease import (
    PublicationLeaseError,
    assert_paper_publisher,
    cycle_lock_key,
    decide_lease,
    lease_script,
)


def test_placeholder_run_id_is_replaced_by_cloud_run_execution(monkeypatch):
    monkeypatch.setenv("RUN_ID", "cloudrun-scheduled")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "angel-market-scan-job-t9j8j")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    assert resolve_run_id() == "angel-market-scan-job-t9j8j"


def test_placeholder_git_sha_is_rejected(monkeypatch):
    monkeypatch.setenv("GIT_SHA", "cloudrun-image-v1")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT", raising=False)
    with pytest.raises(RuntimeError, match="fake SHA"):
        resolve_git_sha()


def test_source_commit_file_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_SHA", "cloudrun-image-v1")
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    commit = "0e80b18b79f069df1c9813b1e210ef5472ee1a29"
    target = tmp_path / "SOURCE_COMMIT"
    target.write_text(commit + "\n", encoding="utf-8")
    monkeypatch.setattr(
        "tools.cycle_provenance._source_commit_files",
        lambda: [target],
    )
    assert resolve_git_sha() == commit
    assert is_real_git_sha("cloudrun-image-v1") is False


def test_apply_process_provenance_overwrites_placeholders(monkeypatch):
    monkeypatch.setenv("RUN_ID", "cloudrun-scheduled")
    monkeypatch.setenv("GIT_SHA", "cloudrun-image-v1")
    monkeypatch.setenv("CLOUD_RUN_EXECUTION", "angel-market-scan-job-rc4bz")
    monkeypatch.setenv("GITHUB_SHA", "0e80b18b79f069df1c9813b1e210ef5472ee1a29")
    applied = apply_process_provenance()
    assert applied["run_id"] == "angel-market-scan-job-rc4bz"
    assert applied["git_sha"] == "0e80b18b79f069df1c9813b1e210ef5472ee1a29"


def test_live_order_flag_refuses_the_lease(monkeypatch):
    monkeypatch.setenv("ALLOW_LIVE_BROKER_ORDERS", "1")
    with pytest.raises(PublicationLeaseError, match="live-order"):
        assert_paper_publisher()


def test_live_order_authority_one_refuses_the_lease(monkeypatch):
    monkeypatch.delenv("ALLOW_LIVE_BROKER_ORDERS", raising=False)
    monkeypatch.setenv("PAPER_MODE", "1")
    monkeypatch.setenv("LIVE_ORDER_AUTHORITY", "1")
    with pytest.raises(PublicationLeaseError, match="LIVE_ORDER_AUTHORITY"):
        assert_paper_publisher()


def test_second_publisher_is_blocked_and_expired_writer_is_fenced(monkeypatch):
    monkeypatch.delenv("ALLOW_LIVE_BROKER_ORDERS", raising=False)
    monkeypatch.delenv("PLACE_REAL_ORDERS", raising=False)
    monkeypatch.delenv("ANGEL_LIVE_ORDERS", raising=False)
    now = datetime.datetime(2026, 10, 14, 9, 20, tzinfo=datetime.timezone.utc)
    first = decide_lease(
        None,
        writer_id="market_bot",
        execution_id="run-a",
        now=now,
        lease_seconds=900,
    )
    assert first["publish"] is True
    assert first["fencing_token"] == 1
    existing = {
        "owner_id": first["owner_id"],
        "acquired_at": now,
        "lease_duration_sec": 900,
    }
    blocked = decide_lease(
        existing,
        writer_id="market_bot",
        execution_id="run-b",
        now=now + datetime.timedelta(seconds=30),
        lease_seconds=900,
    )
    assert blocked["publish"] is False
    assert blocked["action"] == "blocked"
    fenced = decide_lease(
        existing,
        writer_id="market_bot",
        execution_id="run-b",
        now=now + datetime.timedelta(seconds=901),
        lease_seconds=900,
    )
    assert fenced["publish"] is True
    assert fenced["action"] == "fence"
    assert fenced["fencing_token"] == 2
    assert fenced["owner_id"] != first["owner_id"]


def test_lock_key_is_the_ist_paper_cycle(monkeypatch):
    monkeypatch.setenv("ANGEL_MARKET_SESSION", "EOD")
    moment = datetime.datetime(2026, 10, 14, 3, 45, tzinfo=datetime.timezone.utc)
    assert cycle_lock_key(moment) == "paper-cycle:2026-10-14:EOD"


def test_lease_script_is_transactional_and_names_the_lock_table():
    sql = lease_script()
    assert "BEGIN TRANSACTION" in sql
    assert "transaction_write_lock" in sql
    assert "COMMIT TRANSACTION" in sql
    assert "placeOrder" not in sql
    assert "cloudrun-image-v1" not in sql
