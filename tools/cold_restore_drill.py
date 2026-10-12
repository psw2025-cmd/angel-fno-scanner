#!/usr/bin/env python3
"""
tools/cold_restore_drill.py
Isolated Cold-Restore Drill with SHA-256 Readback.
Simulates a zero-production-impact cold backup and restore drill to temporary storage.
Verifies byte-for-byte readback integrity without touching production files.
"""

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cold_restore_drill() -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    drill_id = f"drill_{int(datetime.now(timezone.utc).timestamp())}"
    temp_base = Path(tempfile.gettempdir()) / drill_id

    try:
        source_dir = temp_base / "source_state"
        backup_dir = temp_base / "backups"
        restore_dir = temp_base / "restored_state"

        source_dir.mkdir(parents=True, exist_ok=True)
        backup_dir.mkdir(parents=True, exist_ok=True)
        restore_dir.mkdir(parents=True, exist_ok=True)

        # 1. Create test artifacts with known content
        sample_files = {
            "ledger.json": json.dumps({"schema": "2.5", "test": True, "ts": timestamp}).encode("utf-8"),
            "model_weights.bin": b"SIMULATED_QUANT_MODEL_BINARY_WEIGHTS_V2_TEST_PAYLOAD",
            "audit_manifest.txt": f"AUDIT_HASH_BASELINE_FOR_{drill_id}".encode("utf-8")
        }

        baseline_digests = {}
        for fname, content in sample_files.items():
            fpath = source_dir / fname
            fpath.write_bytes(content)
            baseline_digests[fname] = compute_sha256(content)

        # 2. Perform Cold Backup Archive
        archive_path = backup_dir / "cold_backup.zip"
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in sample_files:
                zf.write(source_dir / fname, arcname=fname)

        archive_sha = compute_sha256(archive_path.read_bytes())

        # 3. Perform Cold Restore to Isolated Target
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(restore_dir)

        # 4. Verify 100% SHA-256 Readback Match
        restored_digests = {}
        matches = {}
        for fname in sample_files:
            rf = restore_dir / fname
            if not rf.exists():
                matches[fname] = False
                continue
            r_digest = compute_sha256(rf.read_bytes())
            restored_digests[fname] = r_digest
            matches[fname] = (r_digest == baseline_digests[fname])

        all_matched = all(matches.values()) and len(matches) == len(sample_files)

        return {
            "status": "PASS" if all_matched else "FAIL",
            "drill_id": drill_id,
            "timestamp_utc": timestamp,
            "archive_sha256": archive_sha,
            "files_tested": len(sample_files),
            "hashes_matched": all_matched,
            "production_untouched": True,
            "file_digests": baseline_digests
        }

    finally:
        # 5. Clean up temporary drill directory
        if temp_base.exists():
            shutil.rmtree(temp_base, ignore_errors=True)


if __name__ == "__main__":
    result = run_cold_restore_drill()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "PASS" else 1)
