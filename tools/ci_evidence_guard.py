"""Fail-closed verifier for externally collected GitHub CI receipts.

This module does not fetch GitHub data and cannot certify deployment.
A receipt is only useful when bound to the expected exact head SHA.
"""
import re


class ReceiptError(ValueError):
    """The supplied CI receipt does not prove the required checks."""


def verify_ci_receipt(receipt, expected_sha, required_jobs):
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ReceiptError("Expected head must be a full lowercase commit SHA")
    if not isinstance(receipt, dict) or receipt.get("head_sha") != expected_sha:
        raise ReceiptError("CI receipt does not match exact head")
    if receipt.get("status") != "completed" or receipt.get("conclusion") != "success":
        raise ReceiptError("Workflow is not completed successfully")
    if not isinstance(required_jobs, (list, tuple)) or not required_jobs or len(set(required_jobs)) != len(required_jobs):
        raise ReceiptError("Required job names must be unique and nonempty")
    jobs = receipt.get("jobs")
    if not isinstance(jobs, list):
        raise ReceiptError("Missing job evidence")
    for name in required_jobs:
        matches = [job for job in jobs if isinstance(job, dict) and job.get("name") == name]
        if len(matches) != 1:
            raise ReceiptError("Required job missing or duplicated: " + name)
        job = matches[0]
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            raise ReceiptError("Required job not successfully completed: " + name)
        required_steps = job.get("required_steps")
        steps = job.get("steps")
        if not isinstance(required_steps, list) or not required_steps or not isinstance(steps, list):
            raise ReceiptError("Required step evidence absent: " + name)
        for step_name in required_steps:
            matched = [step for step in steps if isinstance(step, dict) and step.get("name") == step_name]
            if len(matched) != 1 or matched[0].get("status") != "completed" or matched[0].get("conclusion") != "success":
                raise ReceiptError("Required step not successfully completed: " + str(step_name))
    return {"head_sha": expected_sha, "required_jobs_verified": list(required_jobs), "status": "CI_RECEIPT_VERIFIED_ONLY"}
