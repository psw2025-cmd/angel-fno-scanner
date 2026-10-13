# tools/run_public_sync.ps1
# Runs a single sync cycle between Google Sheets, Local CSV, GDrive, and GitHub
$ErrorActionPreference = "Continue"

$RepoPath = "C:\AngelFNO_Workstation\agy-repair-20261012"
$ScriptPath = Join-Path $RepoPath "tools\sync_public_log.py"
$PythonExe = "python.exe"

if (-not (Test-Path $ScriptPath)) {
    Write-Error "Sync script not found at $ScriptPath"
    exit 1
}

# Run sync with auto-push
& $PythonExe $ScriptPath --sync --push
