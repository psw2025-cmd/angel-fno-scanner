# run_public_sync.ps1
# Hourly cross-platform auto-sync daemon for AngelFNO
$ErrorActionPreference = "Continue"

$py = "C:\AngelFNO_Workstation\repos\angel-fno-scanner\.venv\Scripts\python.exe"
$syncScript = "C:\AngelFNO_Workstation\tools\sync_trading_sheets.py"
$repoDir = "C:\AngelFNO_Workstation\repos\angel-fno-scanner"

# 1. Sync BigQuery prediction records to Google Sheets
if (Test-Path $syncScript) {
    Write-Host "[1/3] Syncing BigQuery predictions and engine health to Google Sheets..."
    & $py $syncScript
}

# 2. Check and push local git changes if configured
if (Test-Path $repoDir) {
    Write-Host "[2/3] Checking Git remote status..."
    $status = git -C $repoDir status --porcelain
    if ($status) {
        Write-Host "  -> Local uncommitted changes detected. Auto-syncing..."
        git -C $repoDir add -A
        git -C $repoDir commit -m "chore(sync): automated cross-platform sync [skip ci]"
        git -C $repoDir push origin HEAD
    } else {
        Write-Host "  -> Working tree clean."
    }
}

# 3. Mirror WSL Runtime Watchdog state
Write-Host "[3/3] Checking WSL Runtime Watchdog..."
try {
    $wslState = wsl -d Ubuntu-24.04 bash -c "systemctl is-active angel-n8n-watchdog.timer 2>/dev/null || true"
    Write-Host "  -> WSL Watchdog Timer State: $wslState"
} catch {
    Write-Host "  -> WSL check failed: $_"
}

Write-Host "Hourly Public Sync Completed at $(Get-Date -Format o)"
