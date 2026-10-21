"""Runtime budget: the application watchdog must finish before the platform kills the task.

Cloud Run jobs set CLOUD_RUN_JOB. The task timeout is not exposed to the container, so it is
supplied as PLATFORM_TIMEOUT_SECONDS (default 14400, the current job setting). The application
budget is clamped to the platform timeout minus a safety margin so a final publish or shutdown
can complete instead of the task being killed mid-write.
"""
from __future__ import annotations

import os
from typing import Mapping

DEFAULT_APP_BUDGET_SECONDS = 22500
DEFAULT_PLATFORM_TIMEOUT_SECONDS = 14400
SAFETY_MARGIN_SECONDS = 600


def effective_runtime_budget(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    requested = max(1, int(env.get("MAX_RUNTIME_SECONDS", str(DEFAULT_APP_BUDGET_SECONDS))))
    if not env.get("CLOUD_RUN_JOB"):
        return requested
    platform = int(env.get("PLATFORM_TIMEOUT_SECONDS", str(DEFAULT_PLATFORM_TIMEOUT_SECONDS)))
    cap = max(1, platform - SAFETY_MARGIN_SECONDS)
    return min(requested, cap)
