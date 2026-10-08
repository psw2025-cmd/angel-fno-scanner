#!/usr/bin/env python3
"""Controlled local n8n workflow synchronizer.

Run only while the n8n service is stopped. The tool creates a SQLite backup,
repairs missing workflow_history rows, writes workflow definitions, enables
foreign-key enforcement, and refuses to finish with FK violations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "n8n_automation" / "workflows"
PROJECT_ID = "OKyqNwSceCfE62Zq"


def get_db_path():
    if os.name == "nt":
        return Path(r"\\wsl$\Ubuntu-24.04\home\pritam\n8n-data\.n8n\database.sqlite")
    return Path("/home/pritam/n8n-data/.n8n/database.sqlite")


def backup_db(db_path: Path):
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if os.name == "nt":
        out = Path(r"C:\AngelFNO_Workstation\backups") / f"n8n_sync_{stamp}.sqlite"
    else:
        out = Path("/mnt/c/AngelFNO_Workstation/backups") / f"n8n_sync_{stamp}.sqlite"
    out.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(out))
    src.backup(dst)
    dst.close()
    src.close()
    print(f"[BACKUP] {out}")
    return out


def _history_exists(cur, version_id):
    return cur.execute("SELECT 1 FROM workflow_history WHERE versionId=?", (version_id,)).fetchone() is not None


def repair_missing_history(conn):
    cur = conn.cursor()
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    repaired = []
    rows = cur.execute(
        "SELECT id,name,nodes,connections,description,activeVersionId,nodeGroups FROM workflow_entity "
        "WHERE activeVersionId IS NOT NULL"
    ).fetchall()
    for workflow_id, name, nodes, connections, description, version_id, node_groups in rows:
        if _history_exists(cur, version_id):
            continue
        cur.execute(
            """INSERT INTO workflow_history
               (versionId,workflowId,authors,createdAt,updatedAt,nodes,connections,name,autosaved,description,nodeGroups)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (version_id, workflow_id, "[]", now, now, nodes, connections, name, 0,
             description or "", node_groups or "[]"),
        )
        repaired.append(workflow_id)
        print(f"[REPAIRED_HISTORY] {workflow_id} -> {version_id}")
    conn.commit()
    return repaired


def sync_workflows(conn, activate=False):
    cur = conn.cursor()
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    synced = []
    for jf in sorted(WORKFLOWS_DIR.glob("*.json")):
        wf = json.loads(jf.read_text(encoding="utf-8"))
        wf_id = wf["id"]
        wf_name = wf["name"]
        nodes = json.dumps(wf.get("nodes", []), separators=(",", ":"))
        connections = json.dumps(wf.get("connections", {}), separators=(",", ":"))
        settings = json.dumps(wf.get("settings", {}), separators=(",", ":"))
        version_id = str(uuid.uuid4())
        current = cur.execute(
            "SELECT createdAt,versionCounter FROM workflow_entity WHERE id=?", (wf_id,)
        ).fetchone()
        created_at = current[0] if current else now
        version_counter = int(current[1] or 0) + 1 if current else 1

        # Step 1 - workflow_entity first with activeVersionId=NULL (breaks circular FK)
        cur.execute(
            """INSERT INTO workflow_entity
               (id,name,active,nodes,connections,settings,staticData,pinData,versionId,triggerCount,meta,parentFolderId,
                createdAt,updatedAt,isArchived,versionCounter,description,activeVersionId,nodeGroups,sourceWorkflowId)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 name=excluded.name, active=excluded.active, nodes=excluded.nodes,
                 connections=excluded.connections, settings=excluded.settings,
                 versionId=excluded.versionId,
                 updatedAt=excluded.updatedAt, versionCounter=excluded.versionCounter,
                 description=excluded.description""",
            (wf_id, wf_name, 1 if activate else 0, nodes, connections, settings,
             None, None, version_id, len(wf.get("nodes", [])), None, None,
             created_at, now, 0, version_counter,
             "Fail-closed read-only Angel F&O automation", None, "[]", None),
        )
        # Step 2 - workflow_history now safe (workflow_entity.id exists)
        cur.execute(
            """INSERT INTO workflow_history
               (versionId,workflowId,authors,createdAt,updatedAt,nodes,connections,name,autosaved,description,nodeGroups)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (version_id, wf_id, "[]", now, now, nodes, connections, wf_name, 0,
             "Fail-closed read-only Angel F&O automation", "[]"),
        )
        # Step 3 - link activeVersionId now that workflow_history.versionId exists
        cur.execute(
            "UPDATE workflow_entity SET activeVersionId=? WHERE id=?",
            (version_id, wf_id),
        )
        cur.execute(
            """INSERT INTO shared_workflow (workflowId,projectId,role,createdAt,updatedAt)
               VALUES (?,?,?,?,?)
               ON CONFLICT(workflowId,projectId) DO UPDATE SET role=excluded.role,updatedAt=excluded.updatedAt""",
            (wf_id, PROJECT_ID, "workflow:owner", now, now),
        )
        synced.append(wf_id)
        print(f"[SYNCED] {wf_id} -> {version_id}")
    conn.commit()
    return synced


def assert_integrity(conn):
    quick = conn.execute("PRAGMA quick_check").fetchone()[0]
    fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"[DB] quick_check={quick} foreign_key_violations={len(fk)}")
    if quick != "ok" or fk:
        for row in fk:
            print("[FK]", row, file=sys.stderr)
        raise SystemExit(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--repair-history", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    if args.sync or args.repair_history:
        backup_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")

    if args.repair_history or args.sync:
        repair_missing_history(conn)
    if args.sync:
        sync_workflows(conn, activate=False)

    assert_integrity(conn)

    if args.list or not (args.sync or args.repair_history):
        for row in conn.execute(
            "SELECT id,name,active,activeVersionId,versionId,updatedAt FROM workflow_entity ORDER BY name"
        ):
            print(row)
    conn.close()


if __name__ == "__main__":
    main()
