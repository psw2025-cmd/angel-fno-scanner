"""CDX-01 regression: BigQuery load jobs must use a bounded timeout and buffer rows on failure."""
import concurrent.futures
from unittest import mock

import pytest
from google.api_core.exceptions import BadRequest

import angel_prediction_engine as engine


class _Job:
    def __init__(self, exc=None):
        self.exc = exc
        self.timeout_seen = "unset"
        self.cancelled = False

    def result(self, timeout=None):
        self.timeout_seen = timeout
        if self.exc:
            raise self.exc
        return "done"

    def cancel(self):
        self.cancelled = True


def test_result_called_with_default_timeout():
    job = _Job()
    assert engine.bq_job_result(job, "t", [{"a": 1}]) == "done"
    assert job.timeout_seen == engine.DEFAULT_BQ_TIMEOUT_SECONDS
    assert engine.DEFAULT_BQ_TIMEOUT_SECONDS > 0


def test_timeout_buffers_rows_cancels_and_raises_runtime_error():
    job = _Job(concurrent.futures.TimeoutError("hung"))
    rows = [{"a": 1}]
    with mock.patch("scanner.write_local_backup_buffer") as buf:
        with pytest.raises(RuntimeError, match="timed out"):
            engine.bq_job_result(job, "next_day_gap_predictions", rows)
    buf.assert_called_once_with(engine.BQ_DATASET_ID, "next_day_gap_predictions", rows)
    assert job.cancelled is True


def test_api_error_buffers_rows_and_reraises():
    job = _Job(BadRequest("bad"))
    rows = [{"a": 1}]
    with mock.patch("scanner.write_local_backup_buffer") as buf:
        with pytest.raises(BadRequest):
            engine.bq_job_result(job, "t", rows)
    buf.assert_called_once_with(engine.BQ_DATASET_ID, "t", rows)


def test_buffer_failure_does_not_mask_original_error():
    job = _Job(concurrent.futures.TimeoutError("hung"))
    with mock.patch("scanner.write_local_backup_buffer", side_effect=OSError("disk")):
        with pytest.raises(RuntimeError, match="timed out"):
            engine.bq_job_result(job, "t", [])


def test_no_bare_result_calls_on_bigquery_jobs():
    import re
    from pathlib import Path
    src = Path(engine.__file__).read_text(encoding="utf-8")
    bare = [m.group(0) for m in re.finditer(r"load_job\w*\.result\(\s*\)|\)\.result\(\s*\)", src)]
    assert bare == []
