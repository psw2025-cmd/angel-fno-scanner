"""Read user-supplied historical top-gainer observations (not broker ground truth).

The CSV has no expiry, executable price, timestamp, volume or OI. Therefore this
module only provides same-day symbol/side/strike *candidate* comparisons. It
must not report exact option-contract hit rate, profitability or calibration.
"""
import csv
import io
import math
from datetime import datetime


def read_reference(csv_text):
    reader = csv.DictReader(io.StringIO(csv_text))
    expected = ["Date", "CE_Symbol", "CE_Strike", "CE_ChgPct",
                "PE_Symbol", "PE_Strike", "PE_ChgPct"]
    if reader.fieldnames != expected:
        raise ValueError("Unexpected historical reference columns")
    observations = []
    seen = set()
    for line in reader:
        day = datetime.strptime(line["Date"], "%d/%m/%Y").date().isoformat()
        for side in ("CE", "PE"):
            symbol = line[f"{side}_Symbol"].strip().upper()
            strike = float(line[f"{side}_Strike"])
            change = float(line[f"{side}_ChgPct"])
            if not symbol or not math.isfinite(strike) or strike <= 0 or not math.isfinite(change):
                raise ValueError("Invalid historical reference row")
            key = (day, symbol, side, strike)
            if key in seen:
                raise ValueError("Duplicate historical reference observation")
            seen.add(key)
            observations.append({"date": day, "symbol": symbol, "side": side,
                                 "strike": strike, "change_pct": change,
                                 "expiry": None, "observed_ltp": None,
                                 "source_type": "user_supplied_unverified"})
    return observations


def candidate_overlap(predictions, observations):
    """Only a candidate overlap; cannot establish exact contract correctness.

    Predictions require dated, timestamped pre-observation evidence supplied by
    an independent verifier; this function intentionally does not infer it.
    """
    expected = {(p["date"], str(p["symbol"]).upper(), str(p["side"]).upper(),
                 float(p["strike"])) for p in predictions}
    observed = {(r["date"], r["symbol"], r["side"], r["strike"]) for r in observations}
    hits = sorted(expected & observed)
    return {"candidate_overlaps": len(hits), "reference_rows": len(observed),
            "exact_contract_hits": None, "prediction_accuracy": None,
            "reason": "Expiry, snapshot timestamp and executable quote unavailable",
            "matches": [{"date": d, "symbol": s, "side": side, "strike": k}
                        for d, s, side, k in hits]}
