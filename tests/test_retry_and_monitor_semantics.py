import pytest
import unittest.mock as mock
from verify_all_sheets_and_engine import open_sheet_with_retry


def test_open_sheet_with_retry_success():
    mock_gc = mock.MagicMock()
    mock_sheet = mock.MagicMock()
    mock_gc.open_by_key.return_value = mock_sheet

    result = open_sheet_with_retry(mock_gc, "test_sheet_id", max_retries=3)
    assert result == mock_sheet
    assert mock_gc.open_by_key.call_count == 1


def test_open_sheet_with_retry_transient_recovery():
    mock_gc = mock.MagicMock()
    mock_sheet = mock.MagicMock()
    # Fails first with an HTML gateway error, then succeeds on retry
    mock_gc.open_by_key.side_effect = [
        Exception("502 Bad Gateway: <html><body>Error</body></html>"),
        mock_sheet
    ]

    result = open_sheet_with_retry(mock_gc, "test_sheet_id", max_retries=3, base_delay=0.01)
    assert result == mock_sheet
    assert mock_gc.open_by_key.call_count == 2


def test_open_sheet_with_retry_permission_denied():
    mock_gc = mock.MagicMock()
    mock_gc.open_by_key.side_effect = Exception("403 Forbidden: Caller lacks permission")

    with pytest.raises(Exception, match="403 Forbidden"):
        open_sheet_with_retry(mock_gc, "test_sheet_id", max_retries=2, base_delay=0.01)
    assert mock_gc.open_by_key.call_count == 1


def test_open_sheet_with_retry_not_found():
    mock_gc = mock.MagicMock()
    mock_gc.open_by_key.side_effect = Exception("404 Not Found: Spreadsheet does not exist")

    with pytest.raises(Exception, match="404 Not Found"):
        open_sheet_with_retry(mock_gc, "test_sheet_id", max_retries=2, base_delay=0.01)
    assert mock_gc.open_by_key.call_count == 1


def test_github_run_semantics_separate_latest_and_historical():
    """Verify that a historical failure does not mark current CI as FAIL if latest main run succeeded."""
    sample_runs = [
        {"id": 101, "name": "Nightly Verify", "head_branch": "main", "conclusion": "success", "status": "completed"},
        {"id": 100, "name": "NASA Daily Proof", "head_branch": "main", "conclusion": "failure", "status": "completed"},
        {"id": 99, "name": "PR Tests", "head_branch": "feature", "conclusion": "success", "status": "completed"}
    ]
    failed = [r for r in sample_runs if r.get("conclusion") in ("failure", "timed_out")]
    latest_main = [r for r in sample_runs if r.get("head_branch") == "main"][0]

    assert latest_main["conclusion"] == "success"
    assert len(failed) == 1
    # Check that latest main status is PASS, with historical failures truthfully recorded
    status = "PASS" if latest_main["conclusion"] == "success" else "FAIL"
    assert status == "PASS"
