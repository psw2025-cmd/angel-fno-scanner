"""Compare FORENSIC_LIVE symbols with option_predictions_live. Prints counts only."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from angel_prediction_engine import get_bigquery_client, get_gspread_client
from credentials import get_canonical_sheet_id


def main() -> None:
    sheet_id = get_canonical_sheet_id()
    sheet = get_gspread_client().open_by_key(sheet_id)
    forensic = sheet.worksheet("FORENSIC_LIVE")
    symbols = []
    for row in forensic.get("B2:B220"):
        if row and str(row[0]).strip():
            symbols.append(str(row[0]).strip())
    bq = get_bigquery_client()
    rows = bq.query(
        "SELECT symbol FROM `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`"
    ).result()
    bq_symbols = sorted(str(row.symbol).strip() for row in rows)
    sheet_symbols = sorted(symbols)
    report = {
        "forensic_symbol_count": len(sheet_symbols),
        "forensic_unique": len(set(sheet_symbols)),
        "bq_symbol_count": len(bq_symbols),
        "bq_unique": len(set(bq_symbols)),
        "only_in_sheet": len(set(sheet_symbols) - set(bq_symbols)),
        "only_in_bq": len(set(bq_symbols) - set(sheet_symbols)),
        "same_multiset": sheet_symbols == bq_symbols,
    }
    out = Path(__file__).with_name("sheet-bq-consistency.json")
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
