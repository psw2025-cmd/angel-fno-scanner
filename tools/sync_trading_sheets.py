"""
sync_trading_sheets.py
Synchronizes live BigQuery predictions and engine health into Google Sheet 1xyqUcEtXrh1pdJTO2N-UASZf4fssxbq7bfEjOp4LvOY
Tabs updated:
- Live_Predictions: rows from fno-angel-prod-1790444589.fno_predictions.option_predictions_live.
  On an OPEN session the date is today. When market_session_state() is not OPEN, the rows are a stored
  copy from the latest cycle_date and the sheet says they are not a live session.
- Engine_Health: scanner PID, broker HTTP ping, BigQuery row note, NSE clock status, and Task Scheduler states.
  When the clock is not OPEN, gate lines say OUTSIDE_SESSION or NOT_RUN. They do not say PASS.
"""
import os
import sys
import time
import json
import ssl
import socket
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

REPO_DIR = Path(r"C:\AngelFNO_Workstation\repos\angel-fno-scanner")
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

import google.auth
from google.auth.exceptions import TransportError
import gspread
import requests
from google.cloud import bigquery
import market_calendar

IST = ZoneInfo("Asia/Kolkata")
SHEET_ID = "1xyqUcEtXrh1pdJTO2N-UASZf4fssxbq7bfEjOp4LvOY"
PROJECT_ID = "fno-angel-prod-1790444589"
EVIDENCE_DIR = Path(r"C:\AngelFNO_Workstation\evidence")
EVIDENCE_PATH = EVIDENCE_DIR / "trading_sheet_sync_latest.json"

NETWORK_ERRORS = (
    ssl.SSLEOFError,
    ssl.SSLError,
    socket.timeout,
    TimeoutError,
    ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    TransportError,
    gspread.exceptions.APIError,
)

def network_call(operation, retries=5):
    delays = [3, 8, 15, 25, 40]
    for attempt in range(retries):
        try:
            return operation()
        except NETWORK_ERRORS as exc:
            if attempt == retries - 1:
                raise
            delay = delays[min(attempt, len(delays) - 1)]
            print(f"[RETRY] Attempt {attempt+1} failed ({type(exc).__name__}: {exc}), retrying in {delay}s...")
            time.sleep(delay)

def get_utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def get_ist_now():
    return datetime.now(IST)

def get_task_state(task_name):
    try:
        cmd = ["powershell", "-NoProfile", "-Command", f"(Get-ScheduledTask -TaskName '{task_name}' -ErrorAction SilentlyContinue).State"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        state = res.stdout.strip()
        return state if state else "Unknown"
    except Exception as e:
        return f"Error: {e}"

def get_dedicated_scanner_processes():
    try:
        ps_cmd = 'Get-CimInstance Win32_Process -Filter "Name like \'python%\'" | Select-Object ProcessId, CommandLine | ConvertTo-Json'
        res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=10)
        scanner_pids = []
        if res.stdout.strip():
            procs = json.loads(res.stdout)
            if isinstance(procs, dict):
                procs = [procs]
            for p in procs:
                cmd = str(p.get("CommandLine") or "").lower()
                if "universal_supervisor.py" in cmd or "scanner.py" in cmd or "angel_prediction_engine.py" in cmd:
                    scanner_pids.append(f"PID {p.get('ProcessId')} ({Path(cmd.split()[1].strip('\"')).name if len(cmd.split()) > 1 else 'scanner'})")
        return scanner_pids
    except Exception:
        return []

def live_predictions_banner(clock, target_date, row_count):
    status = str(clock.get("status") or "UNKNOWN")
    name = str(clock.get("name") or "")
    date = str(clock.get("date") or "")
    if status == "OPEN":
        return (
            f"OPEN on {date}. The rows below are the session dated {target_date}. "
            f"Row count on this page: {row_count}."
        )
    return (
        f"{status}: {name} on {date}. NSE equity and F&O are not in an OPEN session. "
        f"The rows below are a stored copy of {row_count} rows from latest cycle_date {target_date}. "
        "Not a live session. Not prediction accuracy or profit."
    )


def describe_engine_health(
    clock,
    row_count,
    target_date,
    scanner_pids,
    angel_lat,
    dhan_lat,
    paper_mode,
    live_authority,
    proc_summary,
    bq_latency_ms,
    utc_label,
    ist_label,
    tasks,
):
    """Build Engine_Health rows. A closed clock never uses the verdict PASS."""
    status = str(clock.get("status") or "UNKNOWN")
    name = str(clock.get("name") or "")
    date = str(clock.get("date") or "")
    summary = str(clock.get("summary") or "")
    session_open = status == "OPEN"
    clock_line = f"{status}: {name} on {date}. {summary}".strip()
    gate3_label = "Gate 3 (Session-Date BigQuery Rows)"
    if session_open:
        owner_line = (
            f"OPEN on {date} (09:15-15:40 IST). A live scanner and today's fresh rows are required."
        )
        date_label = "Target session date"
        date_value = str(target_date)
        count_label = "Session BigQuery row count"
        count_value = str(row_count)
        scanner_need = "Yes. Status is OPEN."
        fresh_need = "Yes. Today's fresh rows are required while the status is OPEN."
        parity = f"Copied {row_count} rows for session {target_date}. Copying is not a match proof."
        gate1 = "PASS" if scanner_pids else "FAIL"
        if isinstance(angel_lat, (int, float)) and isinstance(dhan_lat, (int, float)):
            gate2 = "PASS"
        else:
            gate2 = f"FAIL (Angel: {angel_lat}, Dhan: {dhan_lat})"
        if row_count == 219:
            gate3 = f"PASS ({row_count} / 219 for {target_date})"
        else:
            gate3 = f"FAIL ({row_count} rows for {target_date}, expected 219)"
        safety = "VALUES_READ" if paper_mode == "1" and live_authority == "0" else "MISSING_OR_UNSAFE"
        gate4 = safety + "; freshness required"
        overall = "PASS" if row_count == 219 else "WARN_PARTIAL"
    else:
        owner_line = (
            f"{status}: {name} on {date}. {summary} "
            "A live scanner is not required. Today's fresh rows are not required."
        )
        date_label = "Latest stored cycle_date (not a live session)"
        date_value = str(target_date)
        count_label = "Stored row count (not a live session)"
        count_value = (
            f"{row_count} stored rows from latest cycle_date {target_date}. Not a live session."
        )
        scanner_need = "No. A live scanner is not required."
        fresh_need = "No. Today's fresh rows are not required."
        parity = (
            f"Copied {row_count} stored rows from latest cycle_date {target_date}. "
            "Not a live session. Copying is not a match proof, not prediction accuracy, and not profit."
        )
        gate3_label = "Gate 3 (Stored rows, not a live session)"
        gate1 = f"OUTSIDE_SESSION: live scanner is not required while status is {status}."
        gate2 = (
            "OUTSIDE_SESSION: broker ping is not a session gate. "
            f"Angel {angel_lat} ms, Dhan {dhan_lat} ms."
        )
        gate3 = (
            f"NOT_RUN as a live-session row check. OUTSIDE_SESSION {status} {name} on {date}. "
            f"Stored count {row_count} from latest cycle_date {target_date} is not a live session."
        )
        gate4 = (
            f"OUTSIDE_SESSION: freshness is not required while status is {status}. "
            f"PAPER_MODE read as {paper_mode}. LIVE_ORDER_AUTHORITY read as {live_authority}."
        )
        overall = "OUTSIDE_SESSION"
        for label, text in (
            ("gate1", gate1),
            ("gate2", gate2),
            ("gate3", gate3),
            ("gate4", gate4),
            ("overall", overall),
            ("owner_line", owner_line),
            ("count_value", count_value),
        ):
            if "PASS" in str(text):
                raise RuntimeError(f"{label} contained PASS while market status is {status}")

    health_matrix = [
        ["ANGEL FNO - ENGINE HEALTH", ""],
        ["Owner plain language", owner_line],
        ["Report Generated UTC", utc_label],
        ["Report Generated IST", ist_label],
        ["NSE Market Calendar State", clock_line],
        ["Clock status", status],
        ["Clock name", name],
        ["Clock date", date],
        ["Live scanner required", scanner_need],
        ["Today fresh rows required", fresh_need],
        ["BigQuery Project", PROJECT_ID],
        ["BigQuery Dataset", "fno_predictions"],
        ["BigQuery Predictions Table", "option_predictions_live"],
        [date_label, date_value],
        [count_label, count_value],
        ["BigQuery Query Latency (ms)", f"{bq_latency_ms} ms"],
        ["Angel One SmartAPI Latency (ms)", f"{angel_lat} ms"],
        ["Dhan API Latency (ms)", f"{dhan_lat} ms"],
        ["Google Sheet copy note", parity],
        ["Dedicated Scanner / Supervisor PIDs", proc_summary],
        ["Safety Guard: PAPER_MODE", paper_mode],
        ["Safety Guard: LIVE_ORDER_AUTHORITY", live_authority],
        ["", ""],
        ["TASK SCHEDULER MONITOR", "STATE"],
        ["SSOT_MD_Inventory", tasks["SSOT_MD_Inventory"]],
        ["AngelSupervisorTask", tasks["AngelSupervisorTask"]],
        ["AngelFNO-WSL-Runtime-Watchdog", tasks["AngelFNO-WSL-Runtime-Watchdog"]],
        ["AngelFNO-PublicSync-Daemon", tasks["AngelFNO-PublicSync-Daemon"]],
        ["AngelFNO-GitHub-Market-Fallback", tasks["AngelFNO-GitHub-Market-Fallback"]],
        ["", ""],
        ["GATE TRIPWIRE VERIFICATION (ANTI-SHORTCUT)", "RESULT"],
        ["Gate 1 (Dedicated Scanner Process)", gate1],
        ["Gate 2 (Real Broker APIs - Angel & Dhan)", gate2],
        [gate3_label, gate3],
        ["Gate 4 (Data Freshness & Deployed Safety)", gate4],
        ["Sheet verdict", overall],
    ]
    gates = {"gate1": gate1, "gate2": gate2, "gate3": gate3, "gate4": gate4}
    return health_matrix, overall, gates


def measure_broker_api_latency():
    endpoints = {
        "Angel One SmartAPI": "https://apiconnect.angelone.in",
        "Dhan API": "https://api.dhan.co"
    }
    latencies = {}
    for name, url in endpoints.items():
        t0 = time.time()
        try:
            r = requests.get(url, timeout=5)
            lat = round((time.time() - t0) * 1000, 2)
            latencies[name] = {"status": r.status_code, "latency_ms": lat}
        except Exception as e:
            latencies[name] = {"status": "ERROR", "error": str(e)}
    return latencies

def sync():
    start_time = time.time()
    now_ist = get_ist_now()
    clock = market_calendar.market_session_state(now_ist)
    session_open = clock.get("status") == "OPEN"
    market_calendar_label = clock.get("status", "UNKNOWN") + ": " + str(clock.get("summary", ""))

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/bigquery"
    ]
    creds, proj = network_call(lambda: google.auth.default(scopes=scopes))
    gc = network_call(lambda: gspread.authorize(creds))
    sh = network_call(lambda: gc.open_by_key(SHEET_ID))

    # 1. Fetch BigQuery Live Predictions (Market-Aware)
    print(f"[1/3] Fetching predictions from BigQuery (Market State: {market_calendar_label})...")
    bq_client = bigquery.Client(project=PROJECT_ID, credentials=creds)
    bq_start = time.time()

    # Query latest session date available
    q_session_date = """
    SELECT DATE(snapshot_timestamp, 'Asia/Kolkata') as sdate
    FROM `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
    ORDER BY snapshot_timestamp DESC
    LIMIT 1
    """
    latest_sdate_rows = list(bq_client.query(q_session_date).result())
    latest_date = str(latest_sdate_rows[0].sdate) if latest_sdate_rows else ""
    target_date = now_ist.date().isoformat() if session_open else (latest_date or now_ist.date().isoformat())

    query = f"""
    SELECT 
        symbol,
        FORMAT_TIMESTAMP('%Y-%m-%d %H:%M:%S UTC', snapshot_timestamp) as cycle_date,
        expected_gap_pct,
        gap_direction,
        action_rating,
        directional_bias,
        spot_ltp,
        confidence_pct,
        pre_open_conviction_pct
    FROM `fno-angel-prod-1790444589.fno_predictions.option_predictions_live`
    WHERE DATE(snapshot_timestamp, 'Asia/Kolkata') = '{target_date}'
    ORDER BY rank ASC, symbol ASC
    """
    rows = list(bq_client.query(query).result())
    bq_latency_ms = round((time.time() - bq_start) * 1000, 2)
    row_count = len(rows)
    if session_open:
        print(f"  -> Retrieved {row_count} rows for OPEN session {target_date} from BigQuery in {bq_latency_ms} ms")
    else:
        print(
            f"  -> Retrieved {row_count} stored rows from latest cycle_date {target_date}. "
            f"Not a live session. Query took {bq_latency_ms} ms"
        )

    # 2. Update Live_Predictions Tab
    print("[2/3] Updating Live_Predictions worksheet...")
    try:
        ws_live = sh.worksheet("Live_Predictions")
    except gspread.WorksheetNotFound:
        ws_live = network_call(lambda: sh.add_worksheet(title="Live_Predictions", rows=250, cols=12))

    headers = [
        "Symbol",
        "Cycle Date",
        "Predicted Gap %",
        "Gap Direction",
        "Action Rating",
        "Directional Bias",
        "Spot LTP",
        "Confidence %",
        "Pre-Open Conviction %"
    ]
    banner = live_predictions_banner(clock, target_date, row_count)
    data_matrix = [[ "EXCHANGE NOTE", banner, "", "", "", "", "", "", "" ]]
    data_matrix.append(headers)
    for r in rows:
        data_matrix.append([
            str(r.symbol or ""),
            str(r.cycle_date or ""),
            str(r.expected_gap_pct if r.expected_gap_pct is not None else ""),
            str(r.gap_direction or ""),
            str(r.action_rating or ""),
            str(r.directional_bias or ""),
            str(r.spot_ltp if r.spot_ltp is not None else ""),
            str(r.confidence_pct if r.confidence_pct is not None else ""),
            str(r.pre_open_conviction_pct if r.pre_open_conviction_pct is not None else "")
        ])

    blank_tail = [["", "", "", "", "", "", "", "", ""] for _ in range(5)]
    write_matrix = data_matrix + blank_tail
    needed_rows = len(write_matrix) + 5
    if ws_live.row_count < needed_rows:
        network_call(lambda: ws_live.resize(rows=needed_rows, cols=max(ws_live.col_count, len(headers))))

    network_call(lambda: ws_live.update(range_name=f"A1:I{len(write_matrix)}", values=write_matrix, value_input_option="RAW"))
    print(f"  -> Updated Live_Predictions with an exchange note and {len(data_matrix)-2} stored or session rows.")

    # 3. Collect Real-Time Engine Health Data
    print("[3/3] Updating Engine_Health worksheet...")
    scanner_pids = get_dedicated_scanner_processes()
    proc_summary = ", ".join(scanner_pids) if scanner_pids else "No dedicated scanner PID"
    
    broker_stats = measure_broker_api_latency()
    angel_lat = broker_stats.get("Angel One SmartAPI", {}).get("latency_ms", "N/A")
    dhan_lat = broker_stats.get("Dhan API", {}).get("latency_ms", "N/A")

    tasks = {
        "SSOT_MD_Inventory": get_task_state("SSOT_MD_Inventory"),
        "AngelSupervisorTask": get_task_state("AngelSupervisorTask"),
        "AngelFNO-WSL-Runtime-Watchdog": get_task_state("AngelFNO-WSL-Runtime-Watchdog"),
        "AngelFNO-PublicSync-Daemon": get_task_state("AngelFNO-PublicSync-Daemon"),
        "AngelFNO-GitHub-Market-Fallback": get_task_state("AngelFNO-GitHub-Market-Fallback"),
    }

    try:
        ws_health = sh.worksheet("Engine_Health")
    except gspread.WorksheetNotFound:
        ws_health = network_call(lambda: sh.add_worksheet(title="Engine_Health", rows=50, cols=6))

    paper_mode = os.environ["PAPER_MODE"] if "PAPER_MODE" in os.environ else "MISSING"
    live_authority = os.environ["LIVE_ORDER_AUTHORITY"] if "LIVE_ORDER_AUTHORITY" in os.environ else "MISSING"
    health_matrix, overall, gates = describe_engine_health(
        clock,
        row_count,
        target_date,
        scanner_pids,
        angel_lat,
        dhan_lat,
        paper_mode,
        live_authority,
        proc_summary,
        bq_latency_ms,
        get_utc_now(),
        now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        tasks,
    )
    padded = []
    for row in health_matrix:
        cells = list(row) + ["", ""]
        padded.append(cells[:4])
    while len(padded) < 45:
        padded.append(["", "", "", ""])

    if ws_health.row_count < 45 or ws_health.col_count < 4:
        network_call(lambda: ws_health.resize(rows=max(ws_health.row_count, 45), cols=max(ws_health.col_count, 4)))

    network_call(lambda: ws_health.update(range_name="A1:D45", values=padded, value_input_option="RAW"))
    print(f"  -> Updated Engine_Health tab. Sheet verdict: {overall}")

    total_duration = round(time.time() - start_time, 2)
    evidence = {
        "sync_utc": get_utc_now(),
        "sync_ist": now_ist.strftime('%Y-%m-%d %H:%M:%S IST'),
        "market_calendar_state": market_calendar_label,
        "target_session_date": target_date,
        "duration_seconds": total_duration,
        "spreadsheet_id": SHEET_ID,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}",
        "bigquery_session_rows": row_count,
        "row_count_meaning": (
            "live OPEN session" if session_open else "stored rows from latest cycle_date, not a live session"
        ),
        "bq_latency_ms": bq_latency_ms,
        "broker_latencies": {
            "Angel One SmartAPI": angel_lat,
            "Dhan API": dhan_lat
        },
        "tabs_updated": ["Live_Predictions", "Engine_Health"],
        "tasks_monitored": tasks,
        "active_processes": proc_summary,
        "live_scanner_required": bool(clock.get("expect_live_scanner")),
        "fresh_rows_required": bool(clock.get("expect_fresh_rows")),
        "stored_rows_are_live_session": session_open,
        "gates": gates,
        "overall": overall,
        "orders_placed": False,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    with open(EVIDENCE_PATH, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)

    print(json.dumps(evidence, indent=2))
    return evidence

if __name__ == "__main__":
    sync()
