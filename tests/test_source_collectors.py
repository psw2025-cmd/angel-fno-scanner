"""Tests for Source Collectors stable JSON schema and freshness evaluation."""
from datetime import datetime, timezone, timedelta
import pytest

from source_collectors import (
    SourceObservation,
    SourceRegistry,
    SourceStatus,
    redact_secrets,
)


def test_redact_secrets():
    raw = "Connected with api_key='abcd1234efgh5678ijkl' and client_code=PRITAM"
    clean = redact_secrets(raw)
    assert "abcd1234efgh5678ijkl" not in clean
    assert "api_key=[REDACTED]" in clean


def test_source_observation_roundtrip():
    obs = SourceObservation(
        source="ANGEL_BROKER_AUTH",
        observed_at_utc="2026-10-12T03:00:00Z",
        sla_seconds=90,
        run_id="RUN-100",
        git_sha="abcdef123456",
        status=SourceStatus.PASS,
        reason="Authenticated via SmartAPI",
        evidence_path="C:\\Temp\\auth.json",
        incident_id=None,
    )
    d = obs.to_dict()
    assert d["source"] == "ANGEL_BROKER_AUTH"
    assert d["status"] == "PASS"

    restored = SourceObservation.from_dict(d)
    assert restored.source == obs.source
    assert restored.status == obs.status
    assert restored.sla_seconds == 90


def test_registry_freshness_and_stale_transition():
    reg = SourceRegistry(current_git_sha="test_sha", current_run_id="test_run")
    t0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    
    # Record observation with 90s SLA
    reg.record(
        source="UNIVERSE_219",
        status=SourceStatus.PASS,
        reason="219 distinct symbols confirmed",
        evidence_path="proof/universe.json",
        sla_seconds=90,
        observed_at=t0,
    )

    # 45 seconds later -> still PASS
    t1 = t0 + timedelta(seconds=45)
    assert reg.evaluate_freshness("UNIVERSE_219", as_of=t1) == SourceStatus.PASS

    # 120 seconds later -> STALE
    t2 = t0 + timedelta(seconds=120)
    assert reg.evaluate_freshness("UNIVERSE_219", as_of=t2) == SourceStatus.STALE

    # Blocked status does not turn stale
    reg.record(
        source="GCS_WORM",
        status=SourceStatus.BLOCKED,
        reason="Billing disabled",
        evidence_path="proof/billing.json",
        sla_seconds=90,
        observed_at=t0,
    )
    assert reg.evaluate_freshness("GCS_WORM", as_of=t2) == SourceStatus.BLOCKED


def test_feed_export():
    reg = SourceRegistry(current_git_sha="feed_sha", current_run_id="feed_run")
    reg.record("TEST_PASS", SourceStatus.PASS, "OK", "proof.txt", 90)
    reg.record("TEST_FAIL", SourceStatus.FAIL, "Down", "proof.txt", 90)
    feed = reg.export_feed()
    assert feed["total_sources"] == 2
    assert feed["summary"]["PASS"] == 1
    assert feed["summary"]["FAIL"] == 1
    assert len(feed["sources"]) == 2
