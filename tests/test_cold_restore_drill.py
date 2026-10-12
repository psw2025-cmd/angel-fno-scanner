"""Tests for cold-restore drill using real project snapshot and labeled fixtures."""
import pytest
from tools.cold_restore_drill import run_cold_restore_drill


def test_cold_restore_drill_deterministic_pass():
    result = run_cold_restore_drill()
    assert result["status"] == "PASS"
    assert result["hashes_matched"] is True
    assert result["files_tested"] >= 4
    assert result["production_untouched"] is True
    assert result["fixture_restore_labeled"] is True
    assert len(result["real_snapshots_restored"]) >= 1
    assert len(result["archive_sha256"]) == 64
