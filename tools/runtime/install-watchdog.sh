#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
test "$(id -u)" = 0
test -f /opt/n8n-sandbox-service/compose.yaml
test "$(systemctl --machine=pritam@.host --user show n8n.service -p LoadState --value)" = loaded
install -d -m 755 /usr/local/lib/angel-n8n-watchdog
install -m 644 n8n_watchdog.py /usr/local/lib/angel-n8n-watchdog/n8n_watchdog.py
install -m 644 angel-n8n-watchdog.service angel-n8n-watchdog.timer /etc/systemd/system/
install -d -m 700 /var/lib/angel-n8n-watchdog
install -d -o pritam -g pritam /home/pritam/.config/systemd/user/n8n.service.d
printf '[Service]\nRestart=always\nRestartSec=5\n' > /home/pritam/.config/systemd/user/n8n.service.d/recovery.conf
chown pritam:pritam /home/pritam/.config/systemd/user/n8n.service.d/recovery.conf
systemctl --machine=pritam@.host --user daemon-reload
systemctl --machine=pritam@.host --user enable n8n.service
loginctl enable-linger pritam
systemctl daemon-reload
systemctl enable --now docker.service sysbox.service angel-n8n-watchdog.timer
systemctl start angel-n8n-watchdog.service
