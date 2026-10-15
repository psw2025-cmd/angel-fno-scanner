"""BigQuery append-only paper ledger; separate table with unique deterministic prediction key."""
import json
import os
from phase2.option_stream import enforce_paper_mode
from phase2.daily_close import canonical_hash

class PaperPublisher:
    def __init__(self, table_id, *, client=None):
        enforce_paper_mode()
        if not table_id or table_id != os.environ.get("PHASE2_PAPER_LEDGER_TABLE"):
            raise RuntimeError("Explicit paper ledger allowlist required")
        from google.cloud import bigquery
        self.client = client or bigquery.Client()
        self.table_id = table_id
        self.bigquery = bigquery

    def publish_once(self, prediction):
        enforce_paper_mode()
        if prediction.get("mode") != "PAPER" or prediction.get("live_order_authority") != 0:
            raise RuntimeError("Unsafe prediction")
        digest = prediction.get("prediction_hash")
        if not digest or canonical_hash({k: v for k, v in prediction.items() if k != "prediction_hash"}) != digest:
            raise ValueError("Prediction integrity failure")
        # BigQuery does not enforce uniqueness; serialize writers externally and MERGE on the hash.
        query = f"""MERGE `{self.table_id}` T USING (SELECT @hash AS prediction_hash, @payload AS payload_json) S
        ON T.prediction_hash = S.prediction_hash
        WHEN NOT MATCHED THEN INSERT (prediction_hash, payload_json) VALUES (S.prediction_hash, S.payload_json)"""
        cfg = self.bigquery.QueryJobConfig(query_parameters=[
            self.bigquery.ScalarQueryParameter("hash", "STRING", digest),
            self.bigquery.ScalarQueryParameter("payload", "STRING", json.dumps(prediction, sort_keys=True, allow_nan=False)),
        ])
        self.client.query(query, job_config=cfg).result()
        rows = list(self.client.query(f"SELECT COUNT(*) AS n FROM `{self.table_id}` WHERE prediction_hash=@hash", job_config=self.bigquery.QueryJobConfig(query_parameters=[self.bigquery.ScalarQueryParameter("hash", "STRING", digest)])).result())
        if len(rows) != 1 or rows[0].n != 1:
            raise RuntimeError("Paper ledger reconciliation failed")
        return {"prediction_hash": digest, "table": self.table_id, "status": "VERIFIED_PAPER"}
