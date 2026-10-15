"""Provision a dedicated persistent paper ledger; never modify production prediction tables."""
import os
from phase2.option_stream import enforce_paper_mode

def provision():
    enforce_paper_mode()
    from google.cloud import bigquery
    project = os.environ["PHASE2_PAPER_PROJECT_ID"]
    if project == "fno-angel-prod-1790444589":
        raise RuntimeError("Production project forbidden for isolated Phase 2 provisioning")
    client = bigquery.Client(project=project)
    dataset_id = f"{project}.paper_trading_phase2"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"  # BigQuery US multi-region, not Cloud Run us-central1
    client.create_dataset(dataset, exists_ok=True)
    table_id = f"{dataset_id}.prediction_ledger"
    table = bigquery.Table(table_id, schema=[
        bigquery.SchemaField("prediction_hash", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("payload_json", "STRING", mode="REQUIRED"),
    ])
    client.create_table(table, exists_ok=True)
    actual = client.get_table(table_id)
    if [(f.name, f.field_type) for f in actual.schema] != [("prediction_hash", "STRING"), ("payload_json", "STRING")]:
        raise RuntimeError("Paper ledger schema mismatch")
    if actual.location.upper() != "US":
        raise RuntimeError("Paper ledger location mismatch")
    print("PAPER_LEDGER_PROVISIONED", table_id)
    return table_id

if __name__ == "__main__":
    provision()
