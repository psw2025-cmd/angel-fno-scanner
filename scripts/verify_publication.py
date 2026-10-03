"""Read-only end-to-end verification; never dispatches a prediction cycle."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from angel_prediction_engine import get_bigquery_client, get_gspread_client, SHEET_ID, BQ_DATASET_ID
from publication import verify_current_publication


def main():
    client = get_bigquery_client()
    book = get_gspread_client().open_by_key(SHEET_ID)
    identity = verify_current_publication(book, client,
                                          client.dataset(BQ_DATASET_ID).table("option_predictions_live"))
    print(json.dumps({"status": "VERIFIED", **identity}))


if __name__ == "__main__":
    main()
