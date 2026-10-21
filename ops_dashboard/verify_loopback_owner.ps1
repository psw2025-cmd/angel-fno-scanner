param(
    [Parameter(Mandatory = $true)][ValidateRange(1, 65535)][int]$ClientPort,
    [Parameter(Mandatory = $true)][ValidateRange(1, 65535)][int]$ServerPort
)
$ErrorActionPreference = 'Stop'
try {
    $connection = Get-NetTCPConnection -State Established -LocalPort $ClientPort -RemotePort $ServerPort -ErrorAction Stop | Select-Object -First 1
    if (-not $connection) { exit 2 }
    $process = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f [int]$connection.OwningProcess) -ErrorAction Stop
    if (-not $process) { exit 3 }
    $owner = Invoke-CimMethod -InputObject $process -MethodName GetOwnerSid -ErrorAction Stop
    $currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    if ($owner.Sid -and $owner.Sid -eq $currentSid) { [Console]::Write('MATCH'); exit 0 }
    exit 4
}
catch {
    exit 5
}
