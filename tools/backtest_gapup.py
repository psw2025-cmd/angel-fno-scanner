"""Gap-up backtest helper.

This file does not query BigQuery and does not write a proof CSV.
Accuracy stays unmeasured until a prediction timestamped before the
outcome is compared with the later gap. A row count is not accuracy.
This is not live profit.
"""
import json
import sys


def measure(rows):
    usable = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        predicted_at = row.get("predicted_at")
        outcome_at = row.get("outcome_at")
        if not predicted_at or not outcome_at or not (str(predicted_at) < str(outcome_at)):
            continue
        if row.get("predicted_gap_pct") is None or row.get("actual_gap_pct") is None:
            continue
        usable.append(row)
    return {
        "status": "NOT_MEASURED" if not usable else "MEASURED_LOCAL_FIXTURE_ONLY",
        "sample_size": len(usable),
        "accuracy": None,
        "note": "No accuracy percent is printed. This is not live profit.",
    }


def main():
    result = measure([])
    print(json.dumps(result))
    return 2


if __name__ == "__main__":
    sys.exit(main())
