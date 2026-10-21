$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $command = Get-Command python -ErrorAction Stop
    $python = $command.Source
}
$env:ANGEL_FNO_REPO_ROOT = $repo
$env:ANGEL_SUPERVISOR_ROOT = 'C:\AngelFNO_Workstation\angel-agent-supervisor'
Write-Output "Starting private read-only dashboard for $repo"
Write-Output 'Address: http://127.0.0.1:8765/'
Write-Output 'Stop with Ctrl+C. This process binds to loopback only.'
& $python (Join-Path $PSScriptRoot 'server.py')
exit $LASTEXITCODE
