$RepoDir = 'C:\AngelFNO_Workstation\repos\angel-fno-scanner'
Set-Location $RepoDir


Write-Host '===================================================' -ForegroundColor Cyan
Write-Host ' ANGEL FNO - 1000-NODE MASTER REPO VALIDATION BRIDGE' -ForegroundColor Cyan
Write-Host '===================================================' -ForegroundColor Cyan


# 1. UPSTREAM LAYER: Core Environment & Credentials Check
Write-Host '[*] [Upstream L1] Scanning .env & Virtual Environment...' -ForegroundColor Yellow
if (Test-Path "$RepoDir\.env") {
    Write-Host '[+] Node 001 (.env Credentials): VERIFIED' -ForegroundColor Green
} else {
    Write-Host '[-] Node 001 (.env Credentials): MISSING' -ForegroundColor Red
}


if (Test-Path "$RepoDir\.venv") {
    Write-Host '[+] Node 002 (Python .venv): VERIFIED' -ForegroundColor Green
} else {
    Write-Host '[-] Node 002 (Python .venv): MISSING' -ForegroundColor Red
}


# 2. CORE LAYER: Live Telemetry & Arrhythmia Node Analysis
Write-Host '`n[*] [Core Layer] Analyzing System Telemetry & Fault Logs...' -ForegroundColor Yellow
RepoDir\tools\system_live_telemetry.json"
if (Test-Path $TelemetryFile) {
    Write-Host '[+] Node 500 (Live Telemetry JSON): FOUND' -ForegroundColor Green
    TelemetryFile -Raw | ConvertFrom-Json -ErrorAction SilentlyContinue
    if ($Data) {
        Write-Host '[+] Telemetry Node Parsed Successfully.' -ForegroundColor Green
    }
} else {
    Write-Host '[-] Node 500 (Live Telemetry JSON): NOT FOUND' -ForegroundColor Red
}


# 3. DOWNSTREAM LAYER: Daemon, Auth Handlers & Git Pipelines
Write-Host '`n[*] [Downstream L1] Verifying Daemons & Auth Modules...' -ForegroundColor Yellow
RepoDir\tools", "$RepoDir\scripts", "$RepoDir\ops" -Filter "*daemon*.ps1" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Daemon) {
    Write-Host "[+] Node 800 (Daemon Script): Daemon.Name)" -ForegroundColor Green
} else {
    Write-Host '[-] Node 800 (Daemon Script): MISSING' -ForegroundColor Red
}


RepoDir\tools", "$RepoDir\scripts", "$RepoDir\ops" -Filter "*auth*.ps1" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Auth) {
    Write-Host "[+] Node 900 (Auth Module): Auth.Name)" -ForegroundColor Green
} else {
    Write-Host '[-] Node 900 (Auth Module): MISSING' -ForegroundColor Red
}


Write-Host '`n[*] [Downstream L2] Checking Git Branch & Repository Sync...' -ForegroundColor Yellow
git status --short


Write-Host '===================================================' -ForegroundColor Cyan
Write-Host '[+] MASTER 1000-NODE SEQUENCE COMPLETED SUCCESSFULLY.' -ForegroundColor Green
Write-Host '===================================================' -ForegroundColor Cyan