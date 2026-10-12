"""Tests for isolated cold-restore drill."""
import pytest
from tools.cold_restore_drill import run_cold_restore_drill


def test_cold_restore_drill_deterministic_pass():
    result = run_cold_restore_drill()
    assert result["status"] == "PASS"
    assert result["hashes_matched"] is True
    assert result["files_tested"] >= 3
    assert result["production_untouched"] is True
    assert len(result["archive_sha256"]) == 64
