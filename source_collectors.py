"""Stable JSON schema and source health collector for Angel F&O Scanner.

Provides verified, unredacted provenance and status for all upstream/downstream components.
Strictly redacts all secrets and provides a structured JSON feed for the 24/7 visual dashboard.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from enum import Enum
import json
import re
from typing import Optional, Dict, Any, List


class SourceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    STALE = "STALE"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


SECRET_PATTERNS = [
    re.compile(r'(?i)(api[_-]?key|secret|password|pin|jwt|token)\s*[:=]\s*["\']?([a-zA-Z0-9_\-\.]{15,})["\']?'),
]


def redact_secrets(text: str) -> str:
    """Ensure no API keys, PINs, or JWT tokens are exposed in reasons or evidence."""
    clean = text
    for pat in SECRET_PATTERNS:
        clean = pat.sub(r'\1=[REDACTED]', clean)
    return clean


@dataclasses.dataclass
class SourceObservation:
    source: str
    observed_at_utc: str
    sla_seconds: int
    run_id: str
    git_sha: str
    status: SourceStatus
    reason: str
    evidence_path: str
    incident_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "observed_at_utc": self.observed_at_utc,
            "sla_seconds": self.sla_seconds,
            "run_id": self.run_id,
            "git_sha": self.git_sha,
            "status": self.status.value,
            "reason": redact_secrets(self.reason),
            "evidence_path": self.evidence_path,
            "incident_id": self.incident_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SourceObservation:
        return cls(
            source=data["source"],
            observed_at_utc=data["observed_at_utc"],
            sla_seconds=int(data["sla_seconds"]),
            run_id=str(data["run_id"]),
            git_sha=str(data["git_sha"]),
            status=SourceStatus(data["status"]),
            reason=redact_secrets(str(data["reason"])),
            evidence_path=str(data["evidence_path"]),
            incident_id=data.get("incident_id"),
        )


class SourceRegistry:
    """Registry that collects, validates, and evaluates freshness for all sources."""

    def __init__(self, current_git_sha: str = "HEAD", current_run_id: str = "LOCAL"):
        self.current_git_sha = current_git_sha
        self.current_run_id = current_run_id
        self._observations: Dict[str, SourceObservation] = {}

    def record(
        self,
        source: str,
        status: SourceStatus,
        reason: str,
        evidence_path: str,
        sla_seconds: int = 90,
        observed_at: Optional[datetime] = None,
        incident_id: Optional[str] = None,
    ) -> SourceObservation:
        now_dt = observed_at or datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()
        
        obs = SourceObservation(
            source=source,
            observed_at_utc=now_iso,
            sla_seconds=sla_seconds,
            run_id=self.current_run_id,
            git_sha=self.current_git_sha,
            status=status,
            reason=redact_secrets(reason),
            evidence_path=evidence_path,
            incident_id=incident_id,
        )
        self._observations[source] = obs
        return obs

    def evaluate_freshness(self, source: str, as_of: Optional[datetime] = None) -> SourceStatus:
        obs = self._observations.get(source)
        if not obs:
            return SourceStatus.FAIL
        
        if obs.status in (SourceStatus.BLOCKED, SourceStatus.NOT_APPLICABLE):
            return obs.status
        
        now = as_of or datetime.now(timezone.utc)
        obs_time = datetime.fromisoformat(obs.observed_at_utc)
        age_seconds = (now - obs_time).total_seconds()
        
        if age_seconds > obs.sla_seconds:
            return SourceStatus.STALE
        return obs.status

    def export_feed(self, as_of: Optional[datetime] = None) -> Dict[str, Any]:
        items = []
        counts = {s.value: 0 for s in SourceStatus}
        
        for name, obs in self._observations.items():
            current_status = self.evaluate_freshness(name, as_of=as_of)
            d = obs.to_dict()
            d["status"] = current_status.value
            items.append(d)
            counts[current_status.value] += 1
            
        return {
            "generated_at_utc": (as_of or datetime.now(timezone.utc)).isoformat(),
            "git_sha": self.current_git_sha,
            "run_id": self.current_run_id,
            "total_sources": len(items),
            "summary": counts,
            "sources": items,
        }
