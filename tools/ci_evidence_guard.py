"""Fail-closed *structural* checker for GitHub Actions CI receipts.

This module cannot authenticate a GitHub receipt, prove complete pagination, or
certify deployment. The required workflow/job/step contract is maintained here
independently of the untrusted receipt being checked.
"""
import re

# Reviewed against .github/workflows/pr_tests.yml on main (2026-10-23).
# Never obtain mandatory steps from receipt["required_steps"].
TRUSTED_REQUIRED_STEPS = {
    "pytest": (
        "Run python tools/memory_guard.py",
        "Run python tools/chaos_inject.py",
        "Run python -m pytest -q",
    ),
}


class ReceiptError(ValueError):
    """The supplied receipt cannot establish even structural CI completeness."""


def verify_ci_receipt(receipt, expected_sha, required_jobs):
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ReceiptError("Expected head must be a full lowercase commit SHA")
    if not isinstance(receipt, dict) or receipt.get("head_sha") != expected_sha:
        raise ReceiptError("CI receipt does not match exact head")
    if receipt.get("status") != "completed" or receipt.get("conclusion") != "success":
        raise ReceiptError("Workflow is not completed successfully")
    # Caller may not weaken the trusted contract by supplying fewer jobs.
    if not isinstance(required_jobs, (tuple, list)) or (
        len(required_jobs) != len(TRUSTED_REQUIRED_STEPS)
        or set(required_jobs) != set(TRUSTED_REQUIRED_STEPS)
    ):
        raise ReceiptError("Required jobs differ from independently reviewed contract")
    jobs = receipt.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ReceiptError("Missing job evidence")
    seen = set()
    for job in jobs:
        if not isinstance(job, dict) or not isinstance(job.get("name"), str):
            raise ReceiptError("Invalid job evidence")
        name = job["name"]
        if name in seen:
            raise ReceiptError("Duplicate job evidence: " + name)
        seen.add(name)
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            raise ReceiptError("Job not successfully completed: " + name)
        if "required_steps" in job:
            raise ReceiptError("Receipt cannot define its own mandatory steps")
    for name, mandatory_steps in TRUSTED_REQUIRED_STEPS.items():
        matches = [job for job in jobs if job["name"] == name]
        if len(matches) != 1:
            raise ReceiptError("Required job missing: " + name)
        steps = matches[0].get("steps")
        if not isinstance(steps, list):
            raise ReceiptError("Missing step evidence: " + name)
        names = []
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("name"), str):
                raise ReceiptError("Invalid step evidence: " + name)
            names.append(step["name"])
        if len(set(names)) != len(names):
            raise ReceiptError("Duplicate step names: " + name)
        # A successful job cannot establish clean evidence while the supplied
        # receipt explicitly reports an unsuccessful additional step.
        for step in steps:
            if step.get("conclusion") in ("failure", "cancelled", "timed_out", "action_required"):
                raise ReceiptError("Unsuccessful observed step: " + step["name"])
        for step_name in mandatory_steps:
            matched = [step for step in steps if step["name"] == step_name]
            if len(matched) != 1 or matched[0].get("status") != "completed" or matched[0].get("conclusion") != "success":
                raise ReceiptError("Required step not successfully completed: " + step_name)
    return {
        "head_sha": expected_sha,
        "required_jobs_verified": list(TRUSTED_REQUIRED_STEPS),
        "status": "CI_RECEIPT_STRUCTURAL_CHECK_ONLY",
        "limitations": "Not authenticated, paginated, deployed, or runtime-proven",
    }
