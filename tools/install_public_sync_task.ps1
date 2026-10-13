param()
$ErrorActionPreference = 'Stop'

$TaskName = 'AngelFNO-PublicSync-Daemon'
$ScriptPath = 'C:\AngelFNO_Workstation\agy-repair-20261012\tools\run_public_sync.ps1'
if (-not (Test-Path $ScriptPath)) {
    throw "Missing runner script: $ScriptPath"
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $ScriptPath)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId ("{0}\{1}" -f $env:USERDOMAIN,$env:USERNAME) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "INSTALLED $TaskName"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State
