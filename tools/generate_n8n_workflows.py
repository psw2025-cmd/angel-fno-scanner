#!/usr/bin/env python3
"""Generate fail-closed n8n workflows for Angel F&O observability.

The workflows are read-only. They never write market data, mutate BigQuery,
change Google Sheets, or place broker orders.
"""
import json
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "n8n_automation" / "workflows"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS = {
    "executionOrder": "v1",
    "timezone": "Asia/Kolkata",
    "saveDataSuccessExecution": "all",
    "saveDataErrorExecution": "all",
    "saveManualExecutions": True,
    "availableInMCP": True,
    "binaryMode": "separate",
}


def schedule(node_id, name, expressions, pos=(-600, 100)):
    return {
        "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": x} for x in expressions]}},
        "id": node_id, "name": name, "type": "n8n-nodes-base.scheduleTrigger",
        "typeVersion": 1.2, "position": list(pos),
    }


def webhook(node_id, name, path, method="GET", pos=(-600, 300)):
    return {
        "parameters": {"path": path, "httpMethod": method, "responseMode": "lastNode", "options": {}},
        "id": node_id, "name": name, "type": "n8n-nodes-base.webhook",
        "typeVersion": 2, "position": list(pos), "webhookId": path + "-webhook",
    }


def exec_trigger(node_id="exec-trigger", name="Execute Workflow Trigger", pos=(-600, 500)):
    return {"parameters": {}, "id": node_id, "name": name,
            "type": "n8n-nodes-base.executeWorkflowTrigger", "typeVersion": 1, "position": list(pos)}


def http(node_id, name, url, timeout, pos):
    return {
        "parameters": {"method": "GET", "url": url, "options": {"timeout": timeout}},
        "id": node_id, "name": name, "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": list(pos),
    }


def code(node_id, name, js, pos):
    return {
        "parameters": {"language": "javaScript", "jsCode": js},
        "id": node_id, "name": name, "type": "n8n-nodes-base.code",
        "typeVersion": 2, "position": list(pos),
    }


def flow(src, dst):
    return {"main": [[{"node": dst, "type": "main", "index": 0}]]}


def wf_master():
    nodes = [
        schedule("master-sched", "Every 5m Market / 15m Off-Peak",
                 ["*/5 9-15 * * 1-5", "*/15 0-8,16-23 * * *"]),
        webhook("master-webhook", "Webhook: Orchestrator Run", "orchestrator-run"),
        exec_trigger("master-exec"),
        http("master-status", "Fetch Verified Orchestrator Status",
             "http://127.0.0.1:5680/orchestrator-status", 120000, (-300, 300)),
        {
            "parameters": {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
                "conditions": [{"id": "healthy", "leftValue": "={{ $json.orchestrator_verdict }}",
                    "rightValue": "HEALTHY", "operator": {"type": "string", "operation": "equals"}}],
                "combinator": "and"}},
            "id": "master-if", "name": "If Verified HEALTHY", "type": "n8n-nodes-base.if",
            "typeVersion": 2.2, "position": [0, 300],
        },
        code("master-ok", "Log Verified Heartbeat", """const d=$input.first().json;
return [{json:{status:"HEALTHY",timestamp_ist:d.timestamp_ist,market_open:d.market_open,
checks:d.checks,read_only:true,message:"All required live checks passed."}}];""", (300, 180)),
        http("master-diagnose", "Diagnose Failure — Read Only",
             "http://127.0.0.1:5680/diagnose", 120000, (300, 420)),
        http("master-reverify", "Independent Re-Verify",
             "http://127.0.0.1:5680/verification-harness", 180000, (560, 420)),
    ]
    con = {
        "Every 5m Market / 15m Off-Peak": flow("", "Fetch Verified Orchestrator Status"),
        "Webhook: Orchestrator Run": flow("", "Fetch Verified Orchestrator Status"),
        "Execute Workflow Trigger": flow("", "Fetch Verified Orchestrator Status"),
        "Fetch Verified Orchestrator Status": flow("", "If Verified HEALTHY"),
        "If Verified HEALTHY": {"main": [
            [{"node": "Log Verified Heartbeat", "type": "main", "index": 0}],
            [{"node": "Diagnose Failure — Read Only", "type": "main", "index": 0}],
        ]},
        "Diagnose Failure — Read Only": flow("", "Independent Re-Verify"),
    }
    return {"id": "angel-fno-master-orchestrator", "name": "Angel FNO Master Continuous Orchestrator — Fail Closed",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


def wf_failure():
    nodes = [
        webhook("fail-webhook", "Webhook: Diagnose Failure", "diagnose-failure", "POST", (-500, 200)),
        exec_trigger("fail-exec", pos=(-500, 400)),
        http("fail-diagnose", "Collect Diagnosis — No Writes", "http://127.0.0.1:5680/diagnose", 120000, (-200, 300)),
        http("fail-harness", "Run Verification Harness", "http://127.0.0.1:5680/verification-harness", 180000, (100, 300)),
        code("fail-eval", "Evaluate Without Auto-Mutation", """const h=$input.first().json;
const passed=Number(h.checks_passed||0); const total=Number(h.checks_total||0);
const exact=total>0 && passed===total && h.verdict==="PASS";
return [{json:{status:exact?"PASS_AFTER_RECHECK":"FAIL_CLOSED_ALERT",checks_passed:passed,
checks_total:total,harness_verdict:h.verdict||"UNKNOWN",read_only:true,
recommended_action:exact?"No mutation required.":"Controlled repair branch required; do not modify production data automatically."}}];""", (420, 300)),
    ]
    con = {
        "Webhook: Diagnose Failure": flow("", "Collect Diagnosis — No Writes"),
        "Execute Workflow Trigger": flow("", "Collect Diagnosis — No Writes"),
        "Collect Diagnosis — No Writes": flow("", "Run Verification Harness"),
        "Run Verification Harness": flow("", "Evaluate Without Auto-Mutation"),
    }
    return {"id": "angel-fno-failure-handler-and-remediation",
            "name": "Angel FNO Failure Handler & Diagnosis — No Writes",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


def wf_powerbi():
    nodes = [
        schedule("pbi-sched", "Every 10m PowerBI Check", ["*/10 * * * *"], (-500, 200)),
        webhook("pbi-webhook", "Webhook: PowerBI Check", "powerbi-check", pos=(-500, 400)),
        http("pbi-http", "Inspect PowerBI Desktop & AS", "http://127.0.0.1:5680/powerbi", 30000, (-200, 300)),
        code("pbi-eval", "Evaluate PowerBI Telemetry", """const d=$input.first().json;
const ok=d.verdict==="HEALTHY" && d.pbi_desktop?.running===true && d.analysis_services?.running===true;
return [{json:{status:ok?"HEALTHY":"DEGRADED",pbi_desktop_running:d.pbi_desktop?.running===true,
analysis_services_running:d.analysis_services?.running===true,listener_ports:(d.analysis_services?.listener_ports||[]).map(p=>p.LocalPort),
verdict:d.verdict||"UNKNOWN",read_only:true}}];""", (100, 300)),
    ]
    con = {"Every 10m PowerBI Check": flow("", "Inspect PowerBI Desktop & AS"),
           "Webhook: PowerBI Check": flow("", "Inspect PowerBI Desktop & AS"),
           "Inspect PowerBI Desktop & AS": flow("", "Evaluate PowerBI Telemetry")}
    return {"id": "angel-fno-powerbi-watchdog", "name": "Angel FNO Power BI Desktop & Analysis Services Watchdog",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


def wf_bq():
    nodes = [
        schedule("bq-sched", "Every 15m BQ Audit", ["*/15 * * * *"], (-500, 200)),
        webhook("bq-webhook", "Webhook: BQ Audit", "bigquery-audit", pos=(-500, 400)),
        http("bq-http", "Inspect BigQuery", "http://127.0.0.1:5680/bigquery", 45000, (-200, 300)),
        code("bq-eval", "Validate BigQuery Lineage", """const d=$input.first().json;
const now=new Date(); const ist=new Date(now.toLocaleString("en-US",{timeZone:"Asia/Kolkata"}));
const wd=ist.getDay(); const mins=ist.getHours()*60+ist.getMinutes(); const market=wd>=1&&wd<=5&&mins>=555&&mins<=930;
const lineage=["with_runid","with_sha","with_writer","with_cycle","with_source_ts"].every(k=>Number(d[k])===219)
 && ["run_ids","git_shas","writer_ids","cycle_ids"].every(k=>Number(d[k])===1);
const universe=Number(d.total_rows)===219 && Number(d.unique_symbols)===219;
const fresh=!market || (typeof d.source_age_seconds==="number" && d.source_age_seconds<=1200);
const ok=universe&&lineage&&fresh;
return [{json:{status:ok?"PASS":"FAIL",total_rows:d.total_rows,unique_symbols:d.unique_symbols,
source_age_seconds:d.source_age_seconds,lineage_complete:lineage,fresh_during_market:fresh,
verdict:ok?"SCHEMA_LINEAGE_FRESHNESS_PASS":"BQ_GATE_FAILED",read_only:true}}];""", (100, 300)),
    ]
    con = {"Every 15m BQ Audit": flow("", "Inspect BigQuery"),
           "Webhook: BQ Audit": flow("", "Inspect BigQuery"),
           "Inspect BigQuery": flow("", "Validate BigQuery Lineage")}
    return {"id": "angel-fno-bigquery-schema-lineage-guardian",
            "name": "Angel FNO BigQuery Schema, Lineage & Freshness Guardian",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


def wf_sheets():
    nodes = [
        schedule("sheet-sched", "Every 10m Sheets Audit", ["*/10 * * * *"], (-500, 200)),
        webhook("sheet-webhook", "Webhook: Sheets Verify", "sheets-verify", pos=(-500, 400)),
        http("sheet-http", "Inspect OPTION_SHEET", "http://127.0.0.1:5680/sheets", 45000, (-200, 300)),
        code("sheet-eval", "Evaluate Sheets Forensic Integrity", """const d=$input.first().json;
const now=new Date(); const ist=new Date(now.toLocaleString("en-US",{timeZone:"Asia/Kolkata"}));
const wd=ist.getDay(); const mins=ist.getHours()*60+ist.getMinutes(); const market=wd>=1&&wd<=5&&mins>=555&&mins<=930;
const universe=Number(d.forensic_live_rows)===219 && Number(d.forensic_live_unique_symbols)===219;
const formulas=Number(d.formula_error_count)===0 && Number(d.failed_gate_count)===0;
const published=d.publication_state==="VERIFIED";
const fresh=!market || (typeof d.heartbeat_age_seconds==="number" && d.heartbeat_age_seconds<=1200);
const ok=universe&&formulas&&published&&fresh;
return [{json:{status:ok?"HEALTHY":"DEGRADED",tab_count:d.total_tabs,
forensic_live_rows:d.forensic_live_rows,forensic_live_unique_symbols:d.forensic_live_unique_symbols,
formula_error_count:d.formula_error_count,failed_gate_count:d.failed_gate_count,
publication_state:d.publication_state,heartbeat_age_seconds:d.heartbeat_age_seconds,
fresh_during_market:fresh,read_only:true}}];""", (100, 300)),
    ]
    con = {"Every 10m Sheets Audit": flow("", "Inspect OPTION_SHEET"),
           "Webhook: Sheets Verify": flow("", "Inspect OPTION_SHEET"),
           "Inspect OPTION_SHEET": flow("", "Evaluate Sheets Forensic Integrity")}
    return {"id": "angel-fno-google-sheet-formula-verifier",
            "name": "Angel FNO Google Sheets Formula, Publication & Freshness Verifier",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


def wf_archive():
    nodes = [
        schedule("archive-sched", "Daily Post-Market 16:15 IST", ["15 16 * * 1-5"], (-500, 200)),
        webhook("archive-webhook", "Webhook: Archive Snapshot", "archive-snapshot", "POST", (-500, 400)),
        http("archive-http", "Run Post-Market Evidence Snapshot", "http://127.0.0.1:5680/post-market", 120000, (-200, 300)),
        code("archive-eval", "Record Snapshot Evidence", """const d=$input.first().json;
const ok=d.status==="success" && Number(d.returncode)===0;
return [{json:{status:ok?"EVIDENCE_CAPTURED":"SNAPSHOT_FAILED",timestamp_ist:new Date().toLocaleString("en-IN",{timeZone:"Asia/Kolkata"}),
evidence:d.evidence||null,read_only:true,note:"No performance or forecast-verification claim is made by this node."}}];""", (100, 300)),
    ]
    con = {"Daily Post-Market 16:15 IST": flow("", "Run Post-Market Evidence Snapshot"),
           "Webhook: Archive Snapshot": flow("", "Run Post-Market Evidence Snapshot"),
           "Run Post-Market Evidence Snapshot": flow("", "Record Snapshot Evidence")}
    return {"id": "angel-fno-operator-snapshot-archiver",
            "name": "Angel FNO Daily Operator Evidence Snapshot",
            "nodes": nodes, "connections": con, "settings": SETTINGS}


WORKFLOWS = [
    ("01_master_continuous_orchestrator.json", wf_master()),
    ("02_failure_handler_and_auto_remediation.json", wf_failure()),
    ("03_powerbi_watchdog.json", wf_powerbi()),
    ("04_bigquery_schema_lineage_guardian.json", wf_bq()),
    ("05_google_sheet_formula_forensic_verifier.json", wf_sheets()),
    ("06_operator_snapshot_archiver.json", wf_archive()),
]


def main():
    for filename, workflow in WORKFLOWS:
        path = OUT_DIR / filename
        path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
        print(f"[WROTE] {path}")


if __name__ == "__main__":
    main()
