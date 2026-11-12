#!/usr/bin/env bash
# Installs ARAH into ./.venv and prepares a .env file. Run from the repository root.
set -euo pipefail

cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "ARAH needs Python 3.11 or newer. On Ubuntu: sudo apt install python3 python3-venv" >&2
  exit 1
fi

"$PY" -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

if [ ! -f .env ]; then
  .venv/bin/arah init
else
  echo ".env already exists, left untouched."
fi

echo
echo "Installed. Next steps:"
echo "  1. Edit .env: add OPENROUTER_API_KEY, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (all optional)."
echo "  2. Check the setup:   .venv/bin/arah doctor"
echo "  3. Start ARAH:        .venv/bin/arah up"
echo "  4. Open the dashboard through an SSH tunnel from your own computer:"
echo "       ssh -L 8787:127.0.0.1:8787 <user>@<your-vps>"
echo "     then visit http://127.0.0.1:8787"
echo "  To keep it running after you log out, see deploy/arah.service."
