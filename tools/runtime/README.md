# Local runtime recovery

This installation reuses the existing `pritam` systemd user service `n8n.service`
and the single `angel-n8n-sandbox` Compose project at
`/opt/n8n-sandbox-service/compose.yaml`. It does not install n8n or another stack.

Install/update in Ubuntu WSL as root with `bash tools/runtime/install-watchdog.sh`.
The installer is idempotent and fails if either existing runtime configuration
is missing. Docker and Sysbox must already be installed and functional.

`angel-n8n-watchdog.timer` checks every 30 seconds after each completed probe:

- n8n port 5678: HTTP 200 and exactly `{"status":"ok"}` at `/healthz`.
- Sandbox port 8080: the same response plus API container health.
- Runner: running and healthy according to Docker's configured readiness probe.

Two consecutive failed checks trigger recovery of only the affected component.
Each component has a four-minute recovery cooldown. Startup is never reported
healthy merely because a restart command completed. Commands are time limited,
overlapping probes are locked out, and state is written atomically.

State: `/var/lib/angel-n8n-watchdog/state.json` (root-only directory).
Logs: `journalctl -u angel-n8n-watchdog.service`.
Timer: `systemctl list-timers angel-n8n-watchdog.timer`.

Windows Task Scheduler task `AngelFNO-WSL-Runtime-Watchdog` invokes:

```text
wsl.exe -d Ubuntu-24.04 -u root -- systemctl start angel-n8n-watchdog.timer
```

Recreate/update this exact task with `tools/runtime/install-windows-watchdog.ps1`
from native Windows PowerShell after installing the WSL timer. The installer
registers the same task name and never creates a second monitoring task.

It runs at ADMIN logon and every two minutes while that user is logged on, with
no stored password and no overlapping instances. It wakes WSL after termination
and relies on the enabled timer/services for recovery. Powered-off, sleeping,
or logged-out Windows cannot be continuously monitored by this task. No claim
of uptime during those states is made.

Disable recovery deliberately before maintenance:
`systemctl disable --now angel-n8n-watchdog.timer` and disable the Windows task.
Restore both after maintenance. A stopped service otherwise counts as failure.
Docker and Sysbox are enabled; both sandbox containers use `unless-stopped`.
n8n's existing service has a drop-in setting `Restart=always` and `RestartSec=5`.

The sandbox API must retain its loopback publication `127.0.0.1:8080:8080`.
The runner and registration endpoints are not published to the host. Credentials
stay in the existing root-owned `.env` and are never copied into this repository.
