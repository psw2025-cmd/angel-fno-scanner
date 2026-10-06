Option Explicit
Dim shell, result
Set shell = CreateObject("WScript.Shell")
result = shell.Run("""C:\Windows\System32\wsl.exe"" -d Ubuntu-24.04 -u root -- sh -c ""systemctl start angel-n8n-watchdog.timer && exec sleep infinity""", 0, True)
WScript.Quit result
