import sqlite3
import json

db_path = "/home/pritam/n8n-data/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Publish all workflows in workflow_published_version
cursor.execute("SELECT id, versionId FROM workflow_entity;")
workflows = cursor.fetchall()
print("Publishing workflows:")
for wid, vid in workflows:
    cursor.execute("""
        INSERT OR REPLACE INTO workflow_published_version (workflowId, publishedVersionId, updatedAt)
        VALUES (?, ?, STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW'));
    """, (wid, vid))
    print(f"  [+] Published {wid} with version {vid}")

# 2. Check workflow_published_version
cursor.execute("SELECT * FROM workflow_published_version;")
print("\nAll published versions now:")
for r in cursor.fetchall():
    print(" ", r)

# 3. Update agent model to google/gemini-flash-latest (or gemini-3.7-flash)
agent_id = "N5WuWeu9TvVSWKiw"
cursor.execute("SELECT schema FROM agents WHERE id = ?;", (agent_id,))
row = cursor.fetchone()
if row:
    schema = json.loads(row[0])
    old_model = schema.get("model")
    # Change model to google/gemini-flash-latest
    schema["model"] = "google/gemini-flash-latest"
    
    # Also update subagents models
    if "subAgents" in schema and "modelsByDifficulty" in schema["subAgents"]:
        for diff in schema["subAgents"]["modelsByDifficulty"]:
            schema["subAgents"]["modelsByDifficulty"][diff]["model"] = "google/gemini-flash-latest"
            
    cursor.execute("UPDATE agents SET schema = ?, updatedAt = STRFTIME('%Y-%m-%d %H:%M:%f', 'NOW') WHERE id = ?;", 
                   (json.dumps(schema), agent_id))
    print(f"\n[+] Updated Agent model from {old_model} to {schema['model']}")

conn.commit()
conn.close()
print("\n[SUCCESS] Applied fixes to database.sqlite")
