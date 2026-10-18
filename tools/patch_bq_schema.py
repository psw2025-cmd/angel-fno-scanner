#!/usr/bin/env python3
import sys
from pathlib import Path
from google.cloud import bigquery
from google.oauth2 import service_account

key_path = Path(r"C:\AngelFNO_Workstation\secrets\gcp-service-account.json")
creds = service_account.Credentials.from_service_account_file(str(key_path))
client = bigquery.Client(credentials=creds, project="fno-angel-prod-1790444589")

table_id = "fno-angel-prod-1790444589.fno_predictions.option_predictions_live"
table = client.get_table(table_id)

has_run_id = any(f.name == "run_id" for f in table.schema)
if not has_run_id:
    print(f"Adding run_id STRING column to {table_id}...")
    new_schema = list(table.schema)
    new_schema.append(bigquery.SchemaField("run_id", "STRING", mode="NULLABLE"))
    table.schema = new_schema
    table = client.update_table(table, ["schema"])
    print("Successfully updated BigQuery table schema via client.update_table!")
else:
    print("run_id already present in schema!")

# Verify
table = client.get_table(table_id)
assert any(f.name == "run_id" for f in table.schema), "Verification failed: run_id still missing"
print("Verification PROVEN: run_id STRING is now present in option_predictions_live schema!")
