#!/usr/bin/env python3
"""
tools/n8n_sync.py

Synchronizes and activates all workflow definitions from n8n_automation/workflows/
directly into the n8n SQLite database (/home/pritam/n8n-data/.n8n/database.sqlite).
Ensures foreign keys in workflow_history and shared_workflow are completely aligned.
"""

import argparse
import datetime
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "n8n_automation" / "workflows"
PROJECT_ID = "OKyqNwSceCfE62Zq"  # Default n8n project id in local environment


def get_db_path():
    if os.name == "nt":
        return Path(r"\\wsl$\Ubuntu-24.04\home\pritam\n8n-data\.n8n\database.sqlite")
    return Path("/home/pritam/n8n-data/.n8n/database.sqlite")


def sync_workflows(conn, activate=True):
    cur = conn.cursor()
    synced = []

    json_files = sorted(WORKFLOWS_DIR.glob("*.json"))
    if not json_files:
        print(f"[WARN] No workflow json files found in {WORKFLOWS_DIR}")
        return synced

    now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            wf = json.load(f)

        wf_id = wf.get("id") or jf.stem.replace("_", "-")
        wf_name = wf.get("name") or jf.stem
        nodes_str = json.dumps(wf.get("nodes", []))
        connections_str = json.dumps(wf.get("connections", {}))
        settings_str = json.dumps(wf.get("settings", {}))
        version_id = str(uuid.uuid4())

        # 1. Insert into workflow_history
        cur.execute(
            """
            INSERT INTO workflow_history (versionId, workflowId, authors, createdAt, updatedAt, nodes, connections, name, autosaved, description, nodeGroups)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, wf_id, "[]", now_utc, now_utc, nodes_str, connections_str, wf_name, 0, "", "[]"),
        )

        # 2. Upsert into workflow_entity
        cur.execute(
            """
            INSERT INTO workflow_entity (
                id, name, active, nodes, connections, settings, staticData, pinData,
                versionId, triggerCount, meta, parentFolderId, createdAt, updatedAt,
                isArchived, versionCounter, description, activeVersionId, nodeGroups, sourceWorkflowId
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                active=excluded.active,
                nodes=excluded.nodes,
                connections=excluded.connections,
                settings=excluded.settings,
                versionId=excluded.versionId,
                activeVersionId=excluded.activeVersionId,
                updatedAt=excluded.updatedAt
            """,
            (
                wf_id,
                wf_name,
                1 if activate else 0,
                nodes_str,
                connections_str,
                settings_str,
                None,
                None,
                version_id,
                len(wf.get("nodes", [])),
                None,
                None,
                now_utc,
                now_utc,
                0,
                1,
                "",
                version_id,
                "[]",
                None,
            ),
        )

        # 3. Upsert shared_workflow
        cur.execute(
            """
            INSERT INTO shared_workflow (workflowId, projectId, role, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workflowId, projectId) DO UPDATE SET
                updatedAt=excluded.updatedAt
            """,
            (wf_id, PROJECT_ID, "workflow:owner", now_utc, now_utc),
        )

        synced.append((wf_id, wf_name))
        print(f"[SYNCED] {wf_name} (ID: {wf_id}, active: {1 if activate else 0})")

    conn.commit()
    return synced


def list_all(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, name, active, triggerCount, updatedAt FROM workflow_entity ORDER BY id")
    rows = cur.fetchall()
    print(f"\nTotal Registered Workflows in n8n: {len(rows)}")
    for r in rows:
        print(f"  - [{r[0]}] {r[1]} (Active: {bool(r[2])}, Nodes/Triggers: {r[3]}, Updated: {r[4]})")


def main():
    parser = argparse.ArgumentParser(description="n8n Database Workflow Sync")
    parser.add_argument("--sync", action="store_true", help="Sync all workflow JSONs into n8n DB")
    parser.add_argument("--list", action="store_true", help="List all registered workflows")
    args = parser.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        print(f"[ERROR] Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))

    if args.sync or (not args.sync and not args.list):
        sync_workflows(conn, activate=True)

    list_all(conn)
    conn.close()


if __name__ == "__main__":
    main()
