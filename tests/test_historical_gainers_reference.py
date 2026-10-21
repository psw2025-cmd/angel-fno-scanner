from pathlib import Path
from historical_gainers_reference import candidate_overlap, read_reference

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "external_reference" / "moneycontrol_user_supplied_oct2026.csv"


def test_reference_13_dates_26_observations():
    rows = read_reference(DATA.read_text(encoding="utf-8"))
    assert len(rows) == 26
    assert len({r["date"] for r in rows}) == 13
    assert len([r for r in rows if r["side"] == "CE"]) == 13
    assert len([r for r in rows if r["side"] == "PE"]) == 13
    assert all(r["expiry"] is None and r["observed_ltp"] is None for r in rows)


def test_overlap_never_claims_exact_contract_hit_or_accuracy():
    rows = read_reference(DATA.read_text(encoding="utf-8"))
    p = [{"date": "2026-10-21", "symbol": "TCS", "side": "CE", "strike": 2660}]
    result = candidate_overlap(p, rows)
    assert result["candidate_overlaps"] == 1
    assert result["exact_contract_hits"] is None
    assert result["prediction_accuracy"] is None


def test_strike_and_date_must_match():
    rows = read_reference(DATA.read_text(encoding="utf-8"))
    p = [{"date": "2026-10-19", "symbol": "TCS", "side": "CE", "strike": 2660}]
    assert candidate_overlap(p, rows)["candidate_overlaps"] == 0
