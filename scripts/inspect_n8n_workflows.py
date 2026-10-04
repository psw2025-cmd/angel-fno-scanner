import sqlite3
import json

db_path = "/home/pritam/n8n-data/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all workflows
cursor.execute("SELECT id, name, active, nodes, connections, settings FROM workflow_entity")
rows = cursor.fetchall()
print(f"Total workflows in database: {len(rows)}")

for r in rows:
    w_id = r["id"]
    w_name = r["name"]
    w_active = bool(r["active"])
    nodes_raw = r["nodes"]
    nodes = json.loads(nodes_raw) if isinstance(nodes_raw, str) else nodes_raw
    settings_raw = r["settings"]
    settings = json.loads(settings_raw) if isinstance(settings_raw, str) else (settings_raw or {})
    
    print("\n" + "="*80)
    print(f"Workflow ID: {w_id}")
    print(f"Workflow Name: {w_name}")
    print(f"Active: {w_active}")
    print(f"Settings: {settings}")
    print(f"Total Nodes: {len(nodes)}")
    
    triggers = []
    has_orders = False
    has_sheets_write = False
    has_bq_write = False
    
    for n in nodes:
        name = n.get("name")
        n_type = n.get("type", "")
        params = n.get("parameters", {})
        
        if "trigger" in n_type.lower() or "schedule" in n_type.lower() or "cron" in n_type.lower() or "webhook" in n_type.lower() or "chat" in n_type.lower():
            triggers.append(f"{name} ({n_type})")
            
        if "sheet" in n_type.lower():
            op = params.get("operation", "")
            if op in ["append", "update", "clear", "delete", "create"]:
                has_sheets_write = True
        if "bigquery" in n_type.lower():
            op = params.get("operation", "")
            if op in ["insert", "update", "delete", "create"]:
                has_bq_write = True
        if "order" in str(params).lower() or "placeorder" in str(params).lower():
            has_orders = True
            
        print(f"  - {name} [{n_type}] (disabled: {n.get('disabled', False)})")
        
    print(f"Triggers: {triggers}")
    print(f"Has Sheets Write: {has_sheets_write}")
    print(f"Has BigQuery Write: {has_bq_write}")
    print(f"Has Orders: {has_orders}")

# Check credentials
cursor.execute("SELECT id, name, type FROM credentials_entity")
creds = cursor.fetchall()
print("\n" + "="*80)
print(f"Credentials Count: {len(creds)}")
for c in creds:
    print(f"  - ID: {c['id']} | Name: {c['name']} | Type: {c['type']}")

# Check executions count
cursor.execute("SELECT COUNT(*) FROM execution_entity")
exec_count = cursor.fetchone()[0]
print(f"Total Executions: {exec_count}")

# Check chat / agents
for t in ["chat_hub_sessions", "chat_hub_messages", "agents", "agents_threads", "agents_messages", "instance_ai_threads", "instance_ai_messages"]:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"Table {t} count: {cnt}")
    except Exception as e:
        print(f"Table {t} error: {e}")
