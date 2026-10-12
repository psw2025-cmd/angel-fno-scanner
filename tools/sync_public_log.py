#!/usr/bin/env python3
"""
tools/sync_public_log.py

Real-Time Multi-Platform Public Sync Engine
Synchronizes public conversation / paper trades log across:
1. Google Sheets (Public Collaborative Master: anyone with link can edit)
   Spreadsheet: OPTION_SHEET (1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs)
   Worksheet: PUBLIC_SYNC_LOG (gid: 1255968385)
2. Local File System: data/public_sync_log.csv
3. Google Drive Local Mount: G:\\My Drive\\AI_Trading_Logs\\public_sync_log.csv (if present)
4. GitHub Repository: data/public_sync_log.csv (auto-committed and pushed)
"""

import os
import sys
import time
import hashlib
import argparse
import subprocess
import urllib.request
from datetime import datetime
from pathlib import Path
import zoneinfo

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CSV_PATH = REPO_ROOT / "data" / "public_sync_log.csv"
GDRIVE_CSV_PATH = Path(r"G:\My Drive\AI_Trading_Logs\public_sync_log.csv")

SHEET_ID = os.environ.get("SHEET_ID", "1Zu_9uJDQdDujsmtavdKnzupL-u2FtQ6C-LlkAswyzcs")
GID = "1255968385"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"

def get_ist_now():
    try:
        tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def fetch_sheet_csv() -> bytes:
    """Fetch CSV directly from Google Sheets public export endpoint."""
    req = urllib.request.Request(
        EXPORT_URL,
        headers={"User-Agent": "AngelFNO-PublicSync/1.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read()

def append_row_to_sheet(platform: str, author: str, message: str, status: str = "CONFIRMED"):
    """Append a row to the Google Sheet using service account credentials."""
    import gspread
    from google.oauth2.service_account import Credentials

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", r"C:\AngelFNO_Workstation\secrets\gcp-service-account.json")
    if not os.path.exists(cred_path):
        raise FileNotFoundError(f"Service account credentials not found at {cred_path}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(cred_path, scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet("PUBLIC_SYNC_LOG")

    timestamp_ist = get_ist_now()
    row = [timestamp_ist, platform, author, message, status]
    ws.append_row(row, value_input_option="USER_ENTERED")
    print(f"[APPEND] Added row to Google Sheet: {row}")
    return row

def sync_once(auto_push: bool = False) -> bool:
    """
    Downloads latest sheet CSV, compares with local, updates files, and git-pushes if changed.
    Returns True if an update was detected and applied.
    """
    LOCAL_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    remote_bytes = fetch_sheet_csv()
    remote_hash = sha256_of_bytes(remote_bytes)

    local_hash = None
    if LOCAL_CSV_PATH.exists():
        with open(LOCAL_CSV_PATH, "rb") as f:
            local_hash = sha256_of_bytes(f.read())

    if local_hash == remote_hash:
        print(f"[{get_ist_now()}] In sync (hash={remote_hash[:8]}). No changes.")
        return False

    print(f"[{get_ist_now()}] Update detected! Local: {str(local_hash)[:8]} -> Remote: {remote_hash[:8]}")
    
    # Write to local repo
    with open(LOCAL_CSV_PATH, "wb") as f:
        f.write(remote_bytes)
    print(f"  -> Written to {LOCAL_CSV_PATH}")

    # Write to Google Drive desktop mount if directory exists
    try:
        if GDRIVE_CSV_PATH.parent.exists():
            with open(GDRIVE_CSV_PATH, "wb") as f:
                f.write(remote_bytes)
            print(f"  -> Written to {GDRIVE_CSV_PATH}")
    except Exception as e:
        print(f"  -> Warning writing to GDrive mount: {e}")

    # Auto commit and push to git if enabled
    if auto_push:
        try:
            print("  -> Committing and pushing to git...")
            subprocess.run(["git", "add", str(LOCAL_CSV_PATH)], cwd=str(REPO_ROOT), check=True)
            msg = f"Auto-sync PUBLIC_SYNC_LOG [{get_ist_now()}]"
            subprocess.run(["git", "commit", "-m", msg], cwd=str(REPO_ROOT), check=True)
            print(f"  -> Committed: {msg}")
            branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=str(REPO_ROOT), text=True).strip() or "main"
            res = subprocess.run(["git", "push", "origin", branch], cwd=str(REPO_ROOT), capture_output=True, text=True)
            if res.returncode == 0:
                print(f"  -> Successfully pushed to GitHub (branch {branch})!")
            else:
                print(f"  -> Git push output: {res.stderr}")
        except Exception as ex:
            print(f"  -> Git commit/push error: {ex}")

    return True

def run_daemon(interval_sec: int = 20, auto_push: bool = False):
    print(f"Starting Public Sync Daemon (interval={interval_sec}s, auto_push={auto_push}). Press Ctrl+C to stop.")
    while True:
        try:
            sync_once(auto_push=auto_push)
        except Exception as e:
            print(f"[{get_ist_now()}] Error during sync: {e}")
        time.sleep(interval_sec)

def main():
    parser = argparse.ArgumentParser(description="Multi-Platform Public Sync Engine")
    parser.add_argument("--sync", action="store_true", help="Run a single sync check")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background")
    parser.add_argument("--interval", type=int, default=20, help="Poll interval in seconds for daemon (default: 20)")
    parser.add_argument("--push", action="store_true", help="Auto git commit and push when changes detected")
    parser.add_argument("--append", nargs=3, metavar=("PLATFORM", "AUTHOR", "MESSAGE"), help="Append a row to Google Sheet and sync")

    args = parser.parse_args()

    if args.append:
        platform, author, msg = args.append
        append_row_to_sheet(platform, author, msg)
        sync_once(auto_push=args.push)
    elif args.daemon:
        run_daemon(interval_sec=args.interval, auto_push=args.push)
    else:
        sync_once(auto_push=args.push)

if __name__ == "__main__":
    main()
