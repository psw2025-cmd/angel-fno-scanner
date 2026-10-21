"""Read-only date span of saved BigQuery spot snapshots. No writes."""
import os

os.environ.setdefault("PAPER_MODE", "1")
os.environ.setdefault("LIVE_ORDER_AUTHORITY", "0")

from angel_prediction_engine import get_bigquery_client

QUERY = """
SELECT table_name
FROM `fno-angel-prod-1790444589.fno_predictions.INFORMATION_SCHEMA.TABLES`
ORDER BY table_name
"""

SPAN = """
SELECT
  COUNT(*) AS n_rows,
  COUNT(DISTINCT DATE(snapshot_timestamp, 'Asia/Kolkata')) AS n_dates,
  CAST(MIN(DATE(snapshot_timestamp, 'Asia/Kolkata')) AS STRING) AS first_date,
  CAST(MAX(DATE(snapshot_timestamp, 'Asia/Kolkata')) AS STRING) AS last_date
FROM `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
"""


def main():
    client = get_bigquery_client()
    print("TABLES")
    for row in client.query(QUERY).result():
        print(row.table_name)
    print("SPAN")
    try:
        for row in client.query(SPAN).result():
            print(dict(row.items()))
    except Exception as exc:
        print("SPAN_ERROR", type(exc).__name__, str(exc)[:500])


if __name__ == "__main__":
    main()
