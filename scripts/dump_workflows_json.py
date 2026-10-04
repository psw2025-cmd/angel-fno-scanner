import sqlite3
import json

db_path = "/home/pritam/n8n-data/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT id, name, active, nodes, connections, settings FROM workflow_entity")
rows = cursor.fetchall()

workflows_export = []
for r in rows:
    nodes = json.loads(r["nodes"]) if isinstance(r["nodes"], str) else r["nodes"]
    connections = json.loads(r["connections"]) if isinstance(r["connections"], str) else r["connections"]
    settings = json.loads(r["settings"]) if isinstance(r["settings"], str) else (r["settings"] or {})
    
    wf = {
        "id": r["id"],
        "name": r["name"],
        "active": bool(r["active"]),
        "nodes": nodes,
        "connections": connections,
        "settings": settings
    }
    workflows_export.append(wf)
    print(f"Exported: {wf['name']} ({len(nodes)} nodes)")

with open("/mnt/c/AngelFNO_Workstation/repos/angel-fno-scanner/audit/n8n_workflows_export.json", "w") as f:
    json.dump(workflows_export, f, indent=2)
print("Saved all workflows to audit/n8n_workflows_export.json")
