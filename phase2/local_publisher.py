"""Offline artifact publisher: BigQuery-formatted MERGE inputs, NOT a BigQuery insertion."""
import json
import os
from pathlib import Path
from phase2.option_stream import enforce_paper_mode
from phase2.daily_close import canonical_hash

class LocalArtifactPublisher:
    def __init__(self, path="receipt.json"):
        enforce_paper_mode()
        self.path = Path(path)

    def publish_once(self, prediction):
        enforce_paper_mode()
        if prediction.get("mode") != "PAPER" or prediction.get("live_order_authority") != 0:
            raise RuntimeError("Unsafe prediction")
        digest = prediction.get("prediction_hash")
        if not digest or canonical_hash({k: v for k, v in prediction.items() if k != "prediction_hash"}) != digest:
            raise ValueError("Prediction integrity failure")
        payload = json.dumps(prediction, sort_keys=True, allow_nan=False)
        receipt = {
            "status": "LOCAL_ARTIFACT_ONLY_NOT_INSERTED",
            "bigquery_insert_id": None,
            "bigquery_job_id": None,
            "prediction_hash": digest,
            "source_hash": prediction["source_hash"],
            "destination_table": os.environ["PHASE2_PAPER_LEDGER_TABLE"],
            "bigquery_merge_parameters": {"hash": digest, "payload": payload},
            "source_kind": os.environ.get("PHASE2_SOURCE_KIND", "UNSPECIFIED"),
            "paper_mode": 1, "live_order_authority": 0,
        }
        self.path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return receipt
