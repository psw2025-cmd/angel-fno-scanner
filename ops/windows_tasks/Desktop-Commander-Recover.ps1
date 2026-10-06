param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$mutex = New-Object Threading.Mutex($false, 'Local\AngelFNODesktopCommanderRecovery')
if (-not $mutex.WaitOne(0)) { Write-Host 'Recovery is already running.'; exit 0 }
try {
    if ($env:USERNAME -ne 'ADMIN') { throw 'Run as the signed-in ADMIN user to reuse the existing device credentials.' }
    $node = 'C:\Program Files\nodejs\node.exe'
    $entry = 'C:\Users\ADMIN\AppData\Local\npm-cache\_npx\e54cca0e4081644e\node_modules\@wonderwhy-er\desktop-commander\dist\index.js'
    if (!(Test-Path -LiteralPath $entry)) {
        $entry = Get-ChildItem "$env:LOCALAPPDATA\npm-cache\_npx\*\node_modules\@wonderwhy-er\desktop-commander\dist\index.js" | Where-Object {
            $package = Get-Content (Join-Path $_.Directory.Parent.FullName 'package.json') -Raw | ConvertFrom-Json
            $package.version -eq '0.2.52'
        } | Select-Object -First 1 -ExpandProperty FullName
    }
    if (!$entry -or !(Test-Path -LiteralPath $node)) { throw 'Existing Node/Commander installation is missing. No software was installed.' }
    if (!(Test-Path "$env:USERPROFILE\.desktop-commander-device\device.json")) { throw 'Saved sign-in is missing. Sign in to Desktop Commander Remote first.' }
    function Find-Connector {
        @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object {
            $_.CommandLine -match 'desktop-commander[\\/]dist[\\/]index\.js["\s]+remote(?:\s|$)'
        })
    }
    $running = @(Find-Connector)
    if ($Restart -and $running.Count) {
        foreach ($process in $running) {
            # Stop only the identified Remote connector and its own child processes.
            & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
            if ($LASTEXITCODE -ne 0) { throw 'Could not stop the existing connector.' }
        }
        Start-Sleep -Seconds 3
        $running = @(Find-Connector)
    }
    $started = $false
    $outLog = Join-Path $PSScriptRoot 'desktop-commander.stdout.log'
    $errLog = Join-Path $PSScriptRoot 'desktop-commander.stderr.log'
    if (!$running.Count) {
        Start-Process -FilePath $node -ArgumentList ('"' + $entry + '" remote') -WorkingDirectory $env:USERPROFILE -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog | Out-Null
        $started = $true
        Write-Host 'Starting Desktop Commander Remote; waiting for connection...'
        Start-Sleep -Seconds 15
    }
    $running = @(Find-Connector)
    if (!$running.Count) { throw 'Connector exited. Inspect the local stderr log; do not share credentials or raw logs.' }
    Write-Host ('RUNNING: Desktop Commander Remote (PID ' + (($running.ProcessId) -join ', ') + ').')
    if ($started -and (Test-Path $outLog) -and (Select-String -LiteralPath $outLog -SimpleMatch 'Desktop Commander Remote is connected' -Quiet)) {
        Write-Host 'CONNECTED: the connector reported a successful Remote connection during this start.'
    } else {
        Write-Host 'ONLINE status is not proven by a process alone. Check https://mcp.desktopcommander.app/.'
        Write-Host 'If the device remains offline, run this batch file with --restart.'
    }
    exit 0
} catch {
    Write-Host ('FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}

