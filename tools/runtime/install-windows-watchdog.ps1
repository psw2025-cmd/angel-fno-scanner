$ErrorActionPreference = 'Stop'
$taskName = 'AngelFNO-WSL-Runtime-Watchdog'
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
& "$env:WINDIR\System32\wsl.exe" -d Ubuntu-24.04 -u root -- test -f /etc/systemd/system/angel-n8n-watchdog.timer
if ($LASTEXITCODE -ne 0) { throw 'Install the WSL watchdog first.' }
$action = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wsl.exe" -Argument '-d Ubuntu-24.04 -u root -- systemctl start angel-n8n-watchdog.timer'
$repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2)
$logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($repeat, $logon) -Principal $principal -Settings $settings -Description 'Wake the existing WSL n8n watchdog while the user is logged on; no stored password.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
