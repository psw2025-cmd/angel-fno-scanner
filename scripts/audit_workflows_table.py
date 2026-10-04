import sqlite3
import json
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

db_path = "/home/pritam/n8n-data/.n8n/database.sqlite"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("""
SELECT workflowId, status, startedAt, stoppedAt 
FROM execution_entity 
ORDER BY id DESC 
LIMIT 50
""")
execs = cursor.fetchall()
print(f"Total executions in recent query: {len(execs)}")
wf_last_run = {}
for e in execs:
    wId = e["workflowId"]
    if wId not in wf_last_run:
        wf_last_run[wId] = {
            "status": e["status"],
            "startedAt": e["startedAt"],
            "stoppedAt": e["stoppedAt"]
        }

print("\nLast run per workflow:")
for wid, data in wf_last_run.items():
    print(f"  {wid}: {data}")

# Check workflow details
cursor.execute("SELECT id, name, active, nodes FROM workflow_entity")
wfs = cursor.fetchall()

print("\n" + "="*100)
print(f"{'Workflow Name':<42} | {'Active':<6} | {'Trigger Type':<25} | {'Write GSheets?':<14} | {'Write BQ?':<10} | {'GH/Scanner?':<12} | {'Order API?':<10} | {'Last Run':<20}")
print("="*100)

for wf in wfs:
    wid = wf["id"]
    name = wf["name"]
    active = "YES" if wf["active"] else "NO"
    nodes = json.loads(wf["nodes"])
    
    triggers = []
    has_sheets_write = "NO (0)"
    has_bq_write = "NO (0)"
    has_gh_dispatch = "NO (0)"
    has_orders = "NO (0)"
    
    for n in nodes:
        ntype = n.get("type", "")
        params = n.get("parameters", {})
        if "scheduleTrigger" in ntype:
            triggers.append("Schedule")
        elif "executeWorkflowTrigger" in ntype:
            triggers.append("Workflow Trigger")
        elif "webhook" in ntype:
            triggers.append("Webhook")
            
        url = params.get("url", "")
        if "github" in url.lower() or "dispatch" in url.lower():
            has_gh_dispatch = "YES"
        if "order" in str(params).lower() or "placeorder" in str(params).lower():
            has_orders = "YES"
            
    trigger_str = ", ".join(set(triggers)) if triggers else "Manual"
    
    last_run_info = wf_last_run.get(wid)
    if last_run_info:
        st = last_run_info["startedAt"]
        status = last_run_info["status"]
        last_run_str = f"{status.upper()} ({st[:19]})"
    else:
        last_run_str = "None (Scheduled)"
        
    print(f"{name:<42} | {active:<6} | {trigger_str:<25} | {has_sheets_write:<14} | {has_bq_write:<10} | {has_gh_dispatch:<12} | {has_orders:<10} | {last_run_str:<20}")
