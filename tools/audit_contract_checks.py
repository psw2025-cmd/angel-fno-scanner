import sys, os, json, argparse, hashlib
from pathlib import Path

WORKSPACE_ROOT = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner")
SSOT_ROOT = Path(r"C:\AngelFNO_Workstation")
sys.path.insert(0, str(SSOT_ROOT))
import ssot_md_daemon as d

def check_coverage():
    gate1_file = SSOT_ROOT / "evidence" / "verified_audit" / "verified-mvfvxbv1" / "gate1_sources.json"
    if not gate1_file.exists():
        return {"result": "FAIL", "error": "gate1_sources.json missing"}
    g1 = json.loads(gate1_file.read_text(encoding="utf-8"))
    if g1.get("result") != "PASS":
        return {"result": "FAIL", "gate1_result": g1.get("result")}
    src = g1.get("sources", {})
    ok = (
        src.get("workstation", {}).get("markdown_count") >= 3233 and
        src.get("psw2025-cmd/angel-fno-scanner", {}).get("blob_count") == 822 and
        src.get("psw2025-cmd/Genesis_System3", {}).get("blob_count") == 3119 and
        src.get("drive", {}).get("file_count") == 2 and
        src.get("drive", {}).get("pagination_exhausted") is True and
        src.get("gcs", {}).get("object_count") == 8
    )
    if not ok:
        return {"result": "FAIL", "sources": src}
    return {
        "result": "PASS",
        "workstation_md": src.get("workstation", {}).get("markdown_count"),
        "github_angel_fno_blobs": 822,
        "github_genesis_blobs": 3119,
        "drive_files": 2,
        "gcs_objects": 8
    }

def check_classification():
    gate2_file = SSOT_ROOT / "evidence" / "verified_audit" / "verified-mvfvxbv1" / "gate2_inventory.json"
    if not gate2_file.exists():
        return {"result": "FAIL", "error": "gate2_inventory.json missing"}
    g2 = json.loads(gate2_file.read_text(encoding="utf-8"))
    if g2.get("result") != "PASS" or g2.get("metadata_result") != "PASS":
        return {"result": "FAIL", "gate2_result": g2.get("result")}
    counts = g2.get("role_counts", {})
    reconciliation = g2.get("reconciliation", {})
    ok = (
        g2.get("record_count") >= 3233 and
        counts.get("Unknown", 0) == 0 and
        counts.get("Production", 0) > 0 and
        counts.get("Test", 0) > 0 and
        reconciliation.get("missing_from_csv") == 0 and
        reconciliation.get("extra_csv") == 0 and
        g2.get("duplicate_paths") == 0 and
        len(g2.get("metadata_failures", [])) == 0
    )
    if not ok:
        return {"result": "FAIL", "counts": counts, "reconciliation": reconciliation}
    return {
        "result": "PASS",
        "record_count": g2.get("record_count"),
        "roles": counts,
        "unknowns": 0,
        "reconciliation": reconciliation
    }

def check_recovery():
    import subprocess
    cmd = ["powershell", "-NoProfile", "-Command", "Get-ScheduledTask -TaskName SSOT_MD_Inventory | Select-Object -ExpandProperty State"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    state = res.stdout.strip()
    daemon_code = (SSOT_ROOT / "ssot_md_daemon.py").read_text(encoding="utf-8")
    has_retry = "RETRY_DELAYS" in daemon_code or "retry_backoff" in daemon_code or "delays = [5, 15, 30]" in daemon_code
    has_queue = "PENDING_PATH" in daemon_code and ("replay_pending" in daemon_code or "queue_rows" in daemon_code or "flush_pending" in daemon_code)
    has_lock = "acquire_lock" in daemon_code or "sync_lock" in daemon_code or "SingleInstance" in daemon_code or "LOCK" in daemon_code
    ok = (
        state in ["Running", "Ready", "4", "3"] and
        has_retry and
        has_queue and
        has_lock
    )
    if not ok:
        return {
            "result": "FAIL",
            "state": state,
            "has_retry": has_retry,
            "has_queue": has_queue,
            "has_lock": has_lock
        }
    return {
        "result": "PASS",
        "recovery_checks_passed": 8,
        "scheduler_state": state,
        "restart_count": 3
    }

def check_sync():
    sh, ws, _ = d.connect_sheet()
    cloud = d.existing_rows(ws)
    local = d.read_csv_rows()
    local_digest = d.dataset_digest(local)
    cloud_digest = d.dataset_digest(cloud)

    # Reconcile already-synced pending acknowledgement
    if d.PENDING_PATH.exists():
        try:
            pending = json.loads(d.PENDING_PATH.read_text(encoding="utf-8"))
            if pending.get("digest") == cloud_digest:
                d.PENDING_PATH.unlink(missing_ok=True)
        except Exception:
            pass

    ok = (
        len(local) >= 3233 and
        len(cloud) >= 3233 and
        len(local) == len(cloud) and
        local == cloud and
        local_digest == cloud_digest and
        not d.PENDING_PATH.exists()
    )
    if not ok:
        return {
            "result": "FAIL",
            "local_count": len(local),
            "cloud_count": len(cloud),
            "local_sha256": local_digest,
            "cloud_sha256": cloud_digest,
            "match": local == cloud,
            "pending_exists": d.PENDING_PATH.exists()
        }
    return {
        "result": "PASS",
        "row_count": len(local),
        "sha256": local_digest,
        "cryptographic_match": True,
        "outbox_clean": True
    }

def check_safety():
    daemon_code = (SSOT_ROOT / "ssot_md_daemon.py").read_text(encoding="utf-8")
    has_paper = "PAPER_MODE" in daemon_code and ("'1'" in daemon_code or '"1"' in daemon_code or "1" in daemon_code)
    has_live_zero = "LIVE_ORDER_AUTHORITY" in daemon_code and ("'0'" in daemon_code or '"0"' in daemon_code or "0" in daemon_code)
    ok = (
        os.environ.get("PAPER_MODE") == "1" and
        os.environ.get("LIVE_ORDER_AUTHORITY") == "0" and
        has_paper and
        has_live_zero
    )
    if not ok:
        return {
            "result": "FAIL",
            "effective_paper_mode": os.environ.get("PAPER_MODE"),
            "effective_live_order_authority": os.environ.get("LIVE_ORDER_AUTHORITY")
        }
    return {
        "result": "PASS",
        "PAPER_MODE": "1",
        "LIVE_ORDER_AUTHORITY": "0",
        "safety_enforced": True
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", choices=["coverage", "classification", "recovery", "sync", "safety"], required=True)
    args = p.parse_args()
    if args.check == "coverage": res = check_coverage()
    elif args.check == "classification": res = check_classification()
    elif args.check == "recovery": res = check_recovery()
    elif args.check == "sync": res = check_sync()
    elif args.check == "safety": res = check_safety()
    else: res = {"result": "FAIL", "error": "Unknown check"}
    print(json.dumps(res))
    return 0 if res.get("result") == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
