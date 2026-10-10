"""Quota-aware, read-only Sheets batching; never substitutes stale data silently."""
import random
import time

def batch_read(spreadsheet, ranges, *, attempts=5, sleep=time.sleep, jitter=random.uniform):
    if not ranges:
        return {}
    if len(set(ranges)) != len(ranges):
        raise ValueError("duplicate sheet range")
    for i in range(attempts):
        try:
            response = spreadsheet.values_batch_get(list(ranges))
            values = response.get("valueRanges", [])
            if len(values) != len(ranges):
                raise RuntimeError("incomplete Sheets batch response")
            return {key: entry.get("values", []) for key, entry in zip(ranges, values)}
        except Exception as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code is None:
                code = getattr(exc, "code", None)
            if str(code) not in ("429", "503") or i == attempts-1:
                raise
            sleep(min(16, 2**i) + jitter(0, 0.25))
    raise RuntimeError("unreachable")
