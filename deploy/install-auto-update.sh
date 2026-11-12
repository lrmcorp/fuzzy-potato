#!/usr/bin/env bash
# Install a systemd timer that runs deploy/vps-auto-update.sh every 5 minutes. Run once as root.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
[ -d "$DIR/.git" ] || { echo "$DIR is not a git checkout; automatic updates need one." >&2; exit 1; }

cat > /etc/systemd/system/arah-update.service <<UNIT
[Unit]
Description=Deploy ARAH when origin/main changes
After=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory=$DIR
Environment=HOME=/root
ExecStart=/usr/bin/env bash $DIR/deploy/vps-auto-update.sh
UNIT
cat > /etc/systemd/system/arah-update.timer <<UNIT
[Unit]
Description=Check for ARAH updates every 5 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
UNIT
# The service runs as root in a checkout that may belong to another user.
git config --global --add safe.directory "$DIR"
systemctl daemon-reload
systemctl enable --now arah-update.timer
echo "Automatic updates are on. Log: journalctl -u arah-update -n 30"
