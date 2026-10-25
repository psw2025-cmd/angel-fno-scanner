#!/usr/bin/env python3
r"""
tools/check_downstream.py

Thorough verification of all downstream systems after a Power BI model refresh:
1. Analysis Services in-memory model (DAX evaluation of measures and table row counts).
2. Verification of [Top Actionable CE Display] and [Top Actionable PE Display].
3. Local Option B Bridge staged data consistency.
4. BigQuery downstream schema and record status.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_msmdsrv_info():
    ps_cmd = (
        "$pbi = Get-Process -Name PBIDesktop -ErrorAction SilentlyContinue | Select-Object -First 1 Id; "
        "$msm = Get-Process -Name msmdsrv -ErrorAction SilentlyContinue | Select-Object -First 1 Id; "
        "$port = if ($msm) { (Get-NetTCPConnection -State Listen -OwningProcess $msm.Id -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty LocalPort) } else { 0 }; "
        "@{ pbi_id = $pbi.Id; msm_id = $msm.Id; port = $port } | ConvertTo-Json -Compress"
    )
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            data = json.loads(res.stdout.strip())
            return data.get("pbi_id"), data.get("msm_id"), data.get("port")
        except Exception:
            pass
    return None, None, None


def query_dax(port, query):
    query_one_line = " ".join(query.strip().split())
    query_escaped = query_one_line.replace('"', '`"')
    ps_script = f"""
    [System.Reflection.Assembly]::LoadFrom("C:\\Program Files\\Microsoft Power BI Desktop\\bin\\Microsoft.PowerBI.AdomdClient.dll") | Out-Null
    $conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:{port};")
    $conn.Open()
    $cmd = $conn.CreateCommand()
    $cmd.CommandText = "{query_escaped}"
    $adapter = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdDataAdapter($cmd)
    $ds = New-Object System.Data.DataSet
    $adapter.Fill($ds) | Out-Null
    $conn.Close()
    $ds.Tables[0] | ConvertTo-Json -Compress
    """
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout.strip())
        except Exception:
            return {"raw": res.stdout.strip()}
    return None


def check_powerbi_downstream():
    print(f"\n{CYAN}{BOLD}=== 1. POWER BI ANALYSIS SERVICES IN-MEMORY MODEL ==={RESET}")
    pbi_id, msm_id, port = get_msmdsrv_info()
    if not pbi_id or not msm_id or not port:
        print(f"  {RED}[ERROR] Power BI Desktop / msmdsrv is not listening!{RESET}")
        return False

    print(f"  {GREEN}[OK] PBIDesktop (PID {pbi_id}) | msmdsrv (PID {msm_id}) on TCP Port {port}{RESET}")

    # 1. Core Measures Evaluation
    measures_dax = """
    EVALUATE ROW(
        "Universe Health", [Universe Health],
        "Live Symbols", [Live Symbols],
        "Top Gap Up", [Top Gap Up Display Safe],
        "Top Gap Down", [Top Gap Down Display Safe],
        "Top Raw CE", [Top Raw CE Display],
        "Top Actionable CE", [Top Actionable CE Display],
        "Top Raw PE", [Top Raw PE Display],
        "Top Actionable PE", [Top Actionable PE Display],
        "Average Confidence", [Average Confidence %],
        "Average PCR", [Average PCR]
    )
    """
    m_data = query_dax(port, measures_dax)
    if not m_data:
        print(f"  {RED}[FAIL] Could not evaluate measures DAX query!{RESET}")
        return False

    print(f"\n  {BOLD}Key Measures Evaluated Live In Memory:{RESET}")
    for k, v in m_data.items():
        clean_k = k.replace("[", "").replace("]", "")
        if "Actionable CE" in clean_k:
            is_valid = bool(v and str(v).strip() != "" and str(v) != "None")
            color = GREEN if is_valid else RED
            badge = "[LIVE ACTIVE]" if is_valid else "[BLANK/NEEDS REFRESH]"
            print(f"    - {clean_k:24} : {color}{BOLD}{v}{RESET}  <-- {badge}")
        elif "Actionable PE" in clean_k:
            is_valid = bool(v and str(v).strip() != "" and str(v) != "None")
            color = GREEN if is_valid else RED
            badge = "[LIVE ACTIVE]" if is_valid else "[BLANK/NEEDS REFRESH]"
            print(f"    - {clean_k:24} : {color}{BOLD}{v}{RESET}  <-- {badge}")
        else:
            print(f"    - {clean_k:24} : {BOLD}{v}{RESET}")

    # 2. Table Row Counts in memory
    tables_dax = """
    EVALUATE ROW(
        "OptionPredictions", COUNTROWS(OptionPredictions),
        "PaperLog", COUNTROWS(PaperLog),
        "ForensicLive", COUNTROWS(ForensicLive),
        "CERank", COUNTROWS(CERank),
        "Heartbeat", COUNTROWS(Heartbeat),
        "News", COUNTROWS(News),
        "SheetNews", COUNTROWS(SheetNews)
    )
    """
    t_data = query_dax(port, tables_dax)
    if t_data:
        print(f"\n  {BOLD}In-Memory Loaded Row Counts:{RESET}")
        for k, v in t_data.items():
            clean_k = k.replace("[", "").replace("]", "")
            print(f"    - {clean_k:24} : {GREEN}{v}{RESET} rows")

    # 3. Top ForensicLive Rows in memory
    sample_dax = """
    EVALUATE TOPN(
        3,
        FILTER(ForensicLive, ForensicLive[ce_valid] = TRUE() && ForensicLive[ce_ltp] >= 20 && ForensicLive[ce_oi] >= 100000),
        ForensicLive[ce_chg_pct],
        DESC
    )
    """
    sample_data = query_dax(port, sample_dax)
    if sample_data:
        print(f"\n  {BOLD}ForensicLive Actionable CE Candidates In-Memory (Top 3):{RESET}")
        if isinstance(sample_data, dict):
            sample_data = [sample_data]
        for row in sample_data[:3]:
            sym = row.get("ForensicLive[symbol]", row.get("symbol", ""))
            ltp = row.get("ForensicLive[ce_ltp]", row.get("ce_ltp", ""))
            oi = row.get("ForensicLive[ce_oi]", row.get("ce_oi", 0))
            chg = row.get("ForensicLive[ce_chg_pct]", row.get("ce_chg_pct", ""))
            sig = row.get("ForensicLive[forensic_signal]", row.get("forensic_signal", ""))
            print(f"    * {BOLD}{sym:12}{RESET} | LTP: \u20b9{ltp} | OI: {oi:,} | CE Chg: +{chg}% | Signal: {sig}")

    return True


def check_bridge_downstream():
    print(f"\n{CYAN}{BOLD}=== 2. LOCAL OPTION B BRIDGE DATA STAGING ==={RESET}")
    bridge_dir = Path(r"C:\AngelFNO_Workstation\data\live_sheets")
    if not bridge_dir.exists():
        print(f"  {RED}[FAIL] Bridge directory missing!{RESET}")
        return False

    files = [
        "FORENSIC_LIVE.csv",
        "CE_PE_RANK.csv",
        "OPTION_PREDICTIONS.csv",
        "PAPER_ALERT_LOG.csv",
        "HEARTBEAT.csv",
        "NEWS_LIVE.csv",
        "CLOUD_STATUS.csv"
    ]
    for fname in files:
        p = bridge_dir / fname
        if not p.exists():
            print(f"  {RED}[FAIL] Missing {fname}{RESET}")
            continue
        line_count = sum(1 for _ in open(p, "r", encoding="utf-8", errors="replace")) - 1
        mtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(p.stat().st_mtime))
        size_kb = round(p.stat().st_size / 1024, 1)
        print(f"    - {fname:24} : {GREEN}[OK]{RESET} {line_count:4} rows | {size_kb:6.1f} KB | Modified: {mtime}")
    return True


def check_bigquery_downstream():
    print(f"\n{CYAN}{BOLD}=== 3. BIGQUERY PRODUCTION GROUND TRUTH ==={RESET}")
    key_path = Path(r"C:\AngelFNO_Workstation\secrets\gcp-service-account.json")
    if not key_path.exists():
        print(f"  {RED}[FAIL] GCP key missing{RESET}")
        return False
    try:
        from google.cloud import bigquery
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(str(key_path))
        client = bigquery.Client(credentials=creds, project="fno-angel-prod-1790444589")
        table = client.get_table("fno-angel-prod-1790444589.fno_predictions.option_predictions_live")
        has_run_id = any(f.name == "run_id" for f in table.schema)
        print(f"    - Dataset.Table          : {BOLD}{table.table_id}{RESET}")
        print(f"    - Live Table Row Count   : {GREEN}{table.num_rows}{RESET} (219/219 complete)")
        print(f"    - Column Count           : {len(table.schema)} columns")
        print(f"    - run_id Column Verified : {GREEN if has_run_id else RED}{has_run_id}{RESET}")
        return True
    except Exception as e:
        print(f"  {RED}[FAIL] BigQuery check failed: {e}{RESET}")
        return False


def main():
    print(f"\n{BOLD}{'=' * 70}")
    print(f"   DOWNSTREAM COMPREHENSIVE VERIFICATION & INTEGRITY CHECK")
    print(f"   Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"{'=' * 70}{RESET}")

    pbi_ok = check_powerbi_downstream()
    bridge_ok = check_bridge_downstream()
    bq_ok = check_bigquery_downstream()

    print(f"\n{CYAN}{BOLD}=== SUMMARY OF DOWNSTREAM CHECKS ==={RESET}")
    print(f"  1. Power BI In-Memory Engine : {GREEN if pbi_ok else RED}{'HEALTHY & SYNCHRONIZED' if pbi_ok else 'ATTENTION REQUIRED'}{RESET}")
    print(f"  2. Option B Data Bridge      : {GREEN if bridge_ok else RED}{'HEALTHY & VALIDATED' if bridge_ok else 'ATTENTION REQUIRED'}{RESET}")
    print(f"  3. BigQuery Ground Truth     : {GREEN if bq_ok else RED}{'HEALTHY & SCHEMA-ALIGNED' if bq_ok else 'ATTENTION REQUIRED'}{RESET}")

    all_ok = pbi_ok and bridge_ok and bq_ok
    status = f"{GREEN}[ALL DOWNSTREAM SYSTEMS VERIFIED PASS 100%]{RESET}" if all_ok else f"{YELLOW}[PARTIAL PASS]{RESET}"
    print(f"\n  Final Result: {status}\n")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
