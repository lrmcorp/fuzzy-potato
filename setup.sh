#!/usr/bin/env bash
# One-step setup for a Linux VPS: packages, install, configuration, background service.
# Run from the repository root:  ./setup.sh
# Answers can also be given up front, for unattended runs:
#   OPENROUTER_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... ./setup.sh
# Optional:
#   ARAH_PASSWORD=...              use this dashboard password instead of a generated one (12+ characters)
#   ARAH_DOMAIN=arah.example.com   serve the dashboard on that domain over HTTPS (installs Caddy)
#   ARAH_AUTO_UPDATE=1             pull new commits from origin/main every 5 minutes and restart
set -euo pipefail
cd "$(dirname "$0")"
DIR="$(pwd)"
USER_NAME="$(id -un)"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

say() { printf '\n== %s\n' "$1"; }

say "1/6 System packages"
if ! command -v python3 >/dev/null || ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
  if command -v apt-get >/dev/null; then
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq python3 python3-venv python3-pip
  else
    echo "Install Python 3.11+ with venv support, then run this script again." >&2; exit 1
  fi
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  echo "ARAH needs Python 3.11 or newer; this machine has $(python3 -V)." >&2; exit 1; }
echo "Python $(python3 -V | cut -d' ' -f2) ready."

say "2/6 Installing ARAH"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .
echo "Installed into $DIR/.venv"

say "3/6 Configuration"
set_env() {  # set_env NAME VALUE: replace the line in .env, or add it
  if grep -q "^$1=" .env; then
    python3 - "$1" "$2" <<'PY'
import sys, pathlib
name, value = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env")
p.write_text("".join(f"{name}={value}\n" if line.startswith(name + "=") else line for line in p.read_text().splitlines(True)))
PY
  else
    printf '%s=%s\n' "$1" "$2" >> .env
  fi
}
ask() {  # ask NAME "question" [secret]: keep an existing or pre-set value, else prompt when a person is there
  local current; current="$(grep "^$1=" .env | cut -d= -f2- || true)"
  local preset="${!1:-}"
  if [ -n "$preset" ]; then set_env "$1" "$preset"; echo "$1: taken from the environment."; return; fi
  if [ -n "$current" ]; then echo "$1: already set, kept."; return; fi
  if [ -t 0 ]; then
    local answer
    if [ "${3:-}" = "secret" ]; then read -r -s -p "$2 (Enter to skip): " answer; echo; else read -r -p "$2 (Enter to skip): " answer; fi
    [ -n "$answer" ] && set_env "$1" "$answer"
  fi
  return 0
}
if [ ! -f .env ]; then .venv/bin/arah init >/dev/null; echo "Created .env with a new dashboard password."; fi
chmod 600 .env
PASSWORD_GIVEN=""
if [ -n "${ARAH_PASSWORD:-}" ]; then
  if [ "${#ARAH_PASSWORD}" -lt 12 ]; then echo "ARAH_PASSWORD must be at least 12 characters." >&2; exit 1; fi
  set_env ARAH_PASSWORD "$ARAH_PASSWORD"; PASSWORD_GIVEN=1
  echo "Dashboard password: set to the one you provided."
fi
ask OPENROUTER_API_KEY "OpenRouter API key, from openrouter.ai/keys" secret
ask TELEGRAM_BOT_TOKEN "Telegram bot token, from @BotFather" secret
ask TELEGRAM_CHAT_ID "Your Telegram chat id, from @userinfobot"
if command -v claude >/dev/null; then
  echo "Claude Code found: it will be used as the fallback when OpenRouter is unavailable."
else
  echo "Claude Code not installed: no fallback. Optional, see README (\"Claude Code as the fallback\")."
fi

say "4/6 Background service"
if command -v systemctl >/dev/null && [ -d /run/systemd/system ]; then
  $SUDO tee /etc/systemd/system/arah.service >/dev/null <<UNIT
[Unit]
Description=ARAH market direction briefings
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/arah up
Restart=on-failure
RestartSec=10
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now arah >/dev/null 2>&1
  $SUDO systemctl restart arah
  sleep 3
  if $SUDO systemctl is-active --quiet arah; then echo "Service 'arah' is running and starts on boot."
  else echo "Service failed to start. See: journalctl -u arah -n 50" >&2; fi
else
  echo "No systemd here. Start ARAH yourself with:  $DIR/.venv/bin/arah up"
fi

say "5/6 Domain and automatic updates"
PORT="$(grep '^ARAH_PORT=' .env | cut -d= -f2)"; PORT="${PORT:-8787}"
DOMAIN="$(printf '%s' "${ARAH_DOMAIN:-}" | tr '[:upper:]' '[:lower:]')"
if [ -n "$DOMAIN" ] && command -v apt-get >/dev/null; then
  command -v caddy >/dev/null || { $SUDO apt-get update -qq; $SUDO apt-get install -y -qq caddy; }
  if ! $SUDO grep -q "^$DOMAIN {" /etc/caddy/Caddyfile 2>/dev/null; then
    [ -f /etc/caddy/Caddyfile ] && $SUDO cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%s)"
    printf '\n%s {\n\tencode gzip\n\treverse_proxy 127.0.0.1:%s\n}\n' "$DOMAIN" "$PORT" | $SUDO tee -a /etc/caddy/Caddyfile >/dev/null
  fi
  $SUDO systemctl enable --now caddy >/dev/null 2>&1 || true
  if $SUDO caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 && $SUDO systemctl reload caddy; then
    echo "HTTPS proxy ready for https://$DOMAIN (the certificate is issued on the first visit; DNS must point here and ports 80 and 443 must be open)."
  else
    echo "Caddy configuration did not validate. Check /etc/caddy/Caddyfile." >&2
  fi
elif [ -n "$DOMAIN" ]; then
  echo "ARAH_DOMAIN is set but this is not a Debian or Ubuntu system: install a reverse proxy to 127.0.0.1:$PORT yourself." >&2
else
  echo "No domain given: the dashboard stays private on 127.0.0.1:$PORT."
fi
if [ "${ARAH_AUTO_UPDATE:-0}" = "1" ] && command -v systemctl >/dev/null && [ -d /run/systemd/system ]; then
  $SUDO tee /etc/systemd/system/arah-update.service >/dev/null <<UNIT
[Unit]
Description=Update ARAH from origin/main

[Service]
Type=oneshot
ExecStart=$DIR/deploy/update.sh
UNIT
  $SUDO tee /etc/systemd/system/arah-update.timer >/dev/null <<UNIT
[Unit]
Description=Check for ARAH updates every 5 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
UNIT
  $SUDO systemctl daemon-reload
  $SUDO systemctl enable --now arah-update.timer >/dev/null 2>&1
  echo "Automatic updates on: every 5 minutes from origin/main. Log: journalctl -u arah-update"
else
  echo "Automatic updates off (set ARAH_AUTO_UPDATE=1 to turn them on)."
fi

say "6/6 Check"
.venv/bin/arah doctor || true

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-your-vps-ip}"
cat <<DONE

ARAH is set up.
  Dashboard password : $( [ -n "$PASSWORD_GIVEN" ] && echo "the one you provided" || grep '^ARAH_PASSWORD=' .env | cut -d= -f2- )
  Open the dashboard : $( [ -n "$DOMAIN" ] && echo "https://$DOMAIN" || echo "ssh -L $PORT:127.0.0.1:$PORT $USER_NAME@$IP  then http://127.0.0.1:$PORT" )
  Telegram           : send /brief to your bot
  Logs               : journalctl -u arah -f
  Change settings    : edit $DIR/.env, then: sudo systemctl restart arah
The first summary appears about a minute after start.
DONE
