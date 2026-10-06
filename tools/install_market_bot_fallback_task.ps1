param()
$ErrorActionPreference = 'Stop'

$TaskName = 'AngelFNO-GitHub-Market-Fallback'
$ScriptPath = 'C:\AngelFNO_Workstation\repos\angel-fno-scanner\tools\ensure_market_bot.ps1'
if (-not (Test-Path $ScriptPath)) {
    throw "Missing fallback script: $ScriptPath"
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $ScriptPath)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Days 3650)
$principal = New-ScheduledTaskPrincipal -UserId ("{0}\{1}" -f $env:USERDOMAIN,$env:USERNAME) -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Output "INSTALLED $TaskName"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName,State
