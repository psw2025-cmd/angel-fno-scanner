@echo off
setlocal
cd /d "%~dp0"
set "GAP_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%GAP_PY%" set "GAP_PY=python"
set "GAP_FAILED=0"
echo Read-only publication prerequisite checks. No predictions or orders will be written.
for %%S in (universe sheets bigquery current export) do (
  "%GAP_PY%" tools\publication_gap_probe.py --stage %%S
  if errorlevel 1 set "GAP_FAILED=1"
)
if "%GAP_FAILED%"=="1" (
  color 4F
  echo Publication prerequisites remain BLOCKED. See audit\publication-gap receipts.
) else (
  echo Read-only prerequisites passed. A new full publication cycle is still unverified.
)
pause
exit /b %GAP_FAILED%
