"""Guarded cleanup and explicit review outcomes for Windows worktrees."""
import json
import time
from pathlib import Path

def cleanup_with_retry(remove, attempts=5, sleep=time.sleep, delays=(2,4,8,8)):
    """Never hide failure or destroy unknown files; caller records pending cleanup."""
    errors=[]
    for i in range(attempts):
        try:
            remove()
            return {"status":"REMOVED","attempts":i+1,"errors":errors}
        except (OSError, RuntimeError) as exc:
            errors.append(str(exc))
            if i+1<attempts:
                sleep(delays[min(i,len(delays)-1)])
    return {"status":"CLEANUP_PENDING","attempts":attempts,"errors":errors}

def review_result(exit_code, output, elapsed, timeout=180):
    """Fail closed; a skipped or timed-out reviewer is never an approval."""
    text=str(output).lower()
    if exit_code==0 and elapsed<timeout and "review_pass" in text and "review_fail" not in text:
        return {"status":"REVIEWED","elapsed":elapsed}
    return {"status":"REVIEW_UNAVAILABLE" if elapsed>=timeout else "REVIEW_FAILED",
            "elapsed":elapsed,"exit_code":exit_code}
