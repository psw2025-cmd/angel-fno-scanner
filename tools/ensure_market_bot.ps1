param()
$ErrorActionPreference = 'Stop'

$RepoRoot = 'C:\AngelFNO_Workstation\repos\angel-fno-scanner'
$Repo = 'psw2025-cmd/angel-fno-scanner'
$Workflow = 'market_bot.yml'
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$ReportDir = 'C:\AngelFNO_Workstation\reports'
$LogFile = Join-Path $ReportDir 'market_bot_fallback.log'

New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null

function Write-AngelLog([string]$Message) {
    $line = ('{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'), $Message)
    Add-Content -Path $LogFile -Value $line
    Write-Output $line
}

$now = Get-Date
if ($now.DayOfWeek -in @('Saturday','Sunday')) {
    Write-AngelLog 'SKIP weekend'
    exit 0
}

Push-Location $RepoRoot
try {
    $marketOpen = & $Python -c "import datetime; from zoneinfo import ZoneInfo; from market_calendar import is_trading_day; z=ZoneInfo('Asia/Kolkata'); n=datetime.datetime.now(z); print('1' if is_trading_day(n) and datetime.time(9,15) <= n.time().replace(tzinfo=None) <= datetime.time(15,30) else '0')"
    if (($marketOpen | Select-Object -Last 1).Trim() -ne '1') {
        Write-AngelLog 'SKIP outside reviewed NSE session or holiday'
        exit 0
    }

    $raw = gh run list --repo $Repo --workflow $Workflow --limit 20 --json databaseId,status,conclusion,createdAt,event,headSha,url
    if ($LASTEXITCODE -ne 0) {
        throw 'gh run list failed'
    }
    $runs = @($raw | ConvertFrom-Json)
    $cutoff = [DateTime]::UtcNow.AddMinutes(-20)

    $recent = @($runs | Where-Object {
        $_.status -in @('queued','in_progress','waiting','pending') -or
        ([DateTime]::Parse($_.createdAt).ToUniversalTime() -ge $cutoff)
    })

    if ($recent.Count -gt 0) {
        $r = $recent | Select-Object -First 1
        Write-AngelLog ("PASS recent/active GitHub market run exists id={0} status={1}" -f $r.databaseId,$r.status)
        exit 0
    }

    Write-AngelLog 'RECOVERY no recent/active market run; dispatching main workflow'
    gh workflow run $Workflow --repo $Repo --ref main
    if ($LASTEXITCODE -ne 0) {
        throw 'gh workflow run failed'
    }
    Start-Sleep -Seconds 3
    $latest = gh run list --repo $Repo --workflow $Workflow --limit 1 --json databaseId,status,createdAt,url | ConvertFrom-Json
    if ($latest) {
        Write-AngelLog ("DISPATCHED id={0} status={1} url={2}" -f $latest.databaseId,$latest.status,$latest.url)
    } else {
        Write-AngelLog 'DISPATCH submitted; run not yet visible'
    }
}
catch {
    Write-AngelLog ("ERROR " + $_.Exception.Message)
    exit 1
}
finally {
    Pop-Location
}
