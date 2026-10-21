"""One-off profile of the already saved gap-prediction extract. Read-only."""
import csv
import collections
from datetime import datetime
from pathlib import Path

path = Path(r"C:\AngelFNO_Workstation\angel-agent-supervisor\logs\PREOPEN_BACKTEST_20261021_bq_gap_rows.csv")
raw = path.read_bytes()
encoding = "utf-16" if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff") else "utf-8-sig"
rows = list(csv.DictReader(path.open(encoding=encoding)))
print("rows", len(rows))
outcomes = collections.Counter((r.get("outcome") or "").strip() or "BLANK" for r in rows)
print("outcomes", dict(outcomes))
dates = sorted({(r.get("prediction_date") or "")[:10] for r in rows})
targets = sorted({(r.get("target_date") or "")[:10] for r in rows})
print("prediction_dates", dates[0], dates[-1], "n", len(dates))
print("target_dates", targets[0], targets[-1], "n", len(targets))
hours = collections.Counter()
for r in rows:
    text = (r.get("predicted_at_ist") or "").strip()
    try:
        stamp = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        hours["BAD"] += 1
        continue
    hours[stamp.strftime("%H")] += 1
print("hours", dict(sorted(hours.items())))
filled_gap = 0
pending_with_gap = 0
for r in rows:
    gap = (r.get("expected_gap_pct") or "").strip()
    outcome = (r.get("outcome") or "").strip()
    if gap and gap not in {"0", "0.0"}:
        if outcome == "PENDING_OPEN":
            pending_with_gap += 1
        else:
            filled_gap += 1
print("pending_with_nonzero_expected_gap", pending_with_gap)
print("other_with_nonzero_expected_gap", filled_gap)
symbols = sorted({(r.get("symbol") or "").strip() for r in rows if (r.get("symbol") or "").strip()})
print("symbols", len(symbols))
vals = []
for r in rows:
    if (r.get("outcome") or "").strip() != "PENDING_OPEN":
        continue
    try:
        vals.append(float(r.get("expected_gap_pct") or "nan"))
    except ValueError:
        continue
vals = [v for v in vals if v == v]
print("pending_expected_n", len(vals))
print("pending_expected_gt_3", sum(1 for v in vals if v > 3))
print("pending_expected_ge_3", sum(1 for v in vals if v >= 3))
print("pending_expected_gt_0", sum(1 for v in vals if v > 0))
if vals:
    print("pending_expected_min", min(vals), "max", max(vals))
