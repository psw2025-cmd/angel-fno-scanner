"""Fail-closed, offline project binding for the read-only staging BigQuery check.

An environment variable is a project selector, NOT proof of authentication or
successful live schema inspection. The caller must still obtain and verify a
genuine BigQuery response. Never log credential values here.
"""
from collections.abc import Mapping


def require_live_bigquery_project(
    environ: Mapping[str, str], expected_project: str
) -> str:
    """Require an explicit, exact project before making any network request."""
    actual = str(environ.get("BQ_PROJECT_ID") or "").strip()
    if not actual:
        raise RuntimeError(
            "BIGQUERY_LIVE_EVIDENCE_BLOCKED: BQ_PROJECT_ID is missing; "
            "live schema validation is not certified"
        )
    if actual != expected_project:
        raise RuntimeError(
            "BIGQUERY_PROJECT_MISMATCH: configured BQ_PROJECT_ID does not "
            "match the approved read-only staging schema target"
        )
    return actual
