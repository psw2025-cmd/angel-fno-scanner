#!/bin/bash
set -eo pipefail
echo "[WSL CHECKER] Running CODEX-1 4-Point Tripwire Verification..."
cmd.exe /c "C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe C:\AngelFNO_Workstation\tools\verify_codex1_gates.py" "$@"
