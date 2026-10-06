#!/usr/bin/env python3
"""
tools/powerbi_inspector.py

Multi-validation inspector for Power BI Desktop and local Analysis Services (msmdsrv).
Checks:
1. PBIDesktop.exe process state, PID, memory, creation time.
2. msmdsrv.exe process state, PID, analysis services port listener.
3. Local report files (.pbix) via Voidtools Everything (es.exe).
4. Emits machine-readable JSON verdict with fail-closed governance.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def query_pbi_telemetry():
    """Execute single optimized PowerShell block to collect PBIDesktop, msmdsrv, and ports."""
    if os.name != "nt":
        return {}, {}, []

    ps_script = (
        "$pbi = Get-Process -Name PBIDesktop -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime, WorkingSet64, Responding; "
        "$msm = Get-Process -Name msmdsrv -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime, WorkingSet64, Responding; "
        "$ports = if ($msm) { Get-NetTCPConnection -State Listen -OwningProcess $msm.Id -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess } else { @() }; "
        "@{ pbi = $pbi; msm = $msm; ports = $ports } | ConvertTo-Json -Compress"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if res.returncode == 0 and res.stdout.strip():
            raw = json.loads(res.stdout.strip())
            pbi = raw.get("pbi")
            msm = raw.get("msm")
            ports = raw.get("ports")

            pbi_list = [pbi] if isinstance(pbi, dict) else (pbi if isinstance(pbi, list) else [])
            msm_list = [msm] if isinstance(msm, dict) else (msm if isinstance(msm, list) else [])
            ports_list = [ports] if isinstance(ports, dict) else (ports if isinstance(ports, list) else [])
            return pbi_list, msm_list, ports_list
    except Exception:
        pass
    return [], [], []


def search_pbix_files():
    """Search for recent .pbix files using es.exe."""
    results = []
    try:
        res = subprocess.run(["es.exe", "-json", "-n", "5", ".pbix"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0 and res.stdout.strip():
            results = json.loads(res.stdout.strip())
    except Exception:
        pass
    return results


def inspect_powerbi():
    pbi_procs, msmdsrv_procs, ports = query_pbi_telemetry()
    pbix_files = search_pbix_files()

    is_pbi_running = len(pbi_procs) > 0
    is_msmdsrv_running = len(msmdsrv_procs) > 0

    verdict = "HEALTHY" if (is_pbi_running and is_msmdsrv_running) else ("PARTIAL" if is_pbi_running else "INACTIVE")

    summary = {
        "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
        "verdict": verdict,
        "pbi_desktop": {
            "running": is_pbi_running,
            "processes": pbi_procs,
        },
        "analysis_services": {
            "running": is_msmdsrv_running,
            "processes": msmdsrv_procs,
            "listener_ports": ports,
        },
        "pbix_files_on_disk": pbix_files,
        "recommendation": (
            "Power BI Desktop is running and connected to Analysis Services."
            if verdict == "HEALTHY"
            else (
                "Launch Power BI Desktop via: Start-Process 'C:\\Program Files\\Microsoft Power BI Desktop\\bin\\PBIDesktop.exe'"
                if not is_pbi_running
                else "PBIDesktop is running but msmdsrv engine is inactive."
            )
        ),
    }
    return summary


def main():
    info = inspect_powerbi()
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
