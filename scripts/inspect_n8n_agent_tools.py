import sqlite3
import json

db_path = "/home/pritam/n8n-data/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

for t in ["agents", "chat_hub_agents", "chat_hub_tools", "chat_hub_agent_tools", "chat_hub_session_tools"]:
    try:
        cursor.execute(f"SELECT * FROM {t}")
        rows = cursor.fetchall()
        print(f"\n=== Table: {t} (count: {len(rows)}) ===")
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"Table {t} error: {e}")

cursor.execute("SELECT id, name, type, parameters FROM credentials_entity")
creds = cursor.fetchall()
print("\n=== Credentials ===")
for c in creds:
    print(f"ID: {c['id']}, Name: {c['name']}, Type: {c['type']}")
