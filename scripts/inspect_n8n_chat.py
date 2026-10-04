import sqlite3

db_path = "/home/pritam/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

for t in ["chat_hub_sessions", "chat_hub_messages", "agents_threads", "agents_messages", "instance_ai_threads", "instance_ai_messages"]:
    try:
        cursor.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        rows = cursor.fetchall()
        print(f"\n=== Table: {t} (count: {len(rows)}) ===")
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"Error reading {t}: {e}")
