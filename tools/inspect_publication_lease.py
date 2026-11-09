"""Read-only BigQuery publication lease diagnostics. Never modifies lock rows."""
import json
import os
from datetime import datetime, timezone
from google.cloud import bigquery

TABLE = "fno-angel-prod-1790444589.fno_predictions.transaction_write_lock"


def main():
    if os.getenv("PAPER_MODE") != "1" or os.getenv("LIVE_ORDER_AUTHORITY", "0") != "0" or os.getenv("REAL_BROKER_ORDERS", "0") != "0":
        raise RuntimeError("PAPER safety guard missing")
    client = bigquery.Client(project="fno-angel-prod-1790444589")
    sql = f"""
    SELECT lock_key, acquired_at, lease_duration_sec,
           TIMESTAMP_ADD(acquired_at, INTERVAL lease_duration_sec SECOND) AS expires_at,
           TIMESTAMP_ADD(acquired_at, INTERVAL lease_duration_sec SECOND) > CURRENT_TIMESTAMP() AS active
    FROM `{TABLE}`
    WHERE lock_key LIKE 'paper-cycle:%'
    ORDER BY acquired_at DESC
    LIMIT 10
    """
    rows = [dict(row.items()) for row in client.query(sql).result()]
    print(json.dumps({"read_only": True, "leases": rows}, default=str))
    if not rows:
        print("NO_LEASE_ROWS")


if __name__ == "__main__":
    main()
