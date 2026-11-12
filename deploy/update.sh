#!/usr/bin/env bash
# Pull origin/main, reinstall, restart, and roll back if the app does not come up.
# Run by arah-update.timer as root; git and pip run as the owner of the checkout.
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
OWNER="$(stat -c %U "$DIR")"
as_owner() { if [ "$(id -un)" = "$OWNER" ]; then "$@"; else runuser -u "$OWNER" -- "$@"; fi; }
cd "$DIR"

as_owner git fetch --quiet origin main
OLD="$(as_owner git rev-parse HEAD)"
NEW="$(as_owner git rev-parse origin/main)"
[ "$OLD" = "$NEW" ] && exit 0

PORT="$(grep '^ARAH_PORT=' .env 2>/dev/null | cut -d= -f2)"; PORT="${PORT:-8787}"
healthy() {
  for _ in $(seq 1 20); do
    curl -fsS -m 5 "http://127.0.0.1:$PORT/api/session" >/dev/null 2>&1 && return 0
    sleep 3
  done
  return 1
}
install_and_restart() {
  as_owner "$DIR/.venv/bin/pip" install --quiet -e "$DIR"
  systemctl restart arah
}

echo "Updating ARAH $OLD -> $NEW"
# Fast-forward only: local edits on the server stop the update instead of being overwritten.
as_owner git merge --ff-only --quiet origin/main
install_and_restart
if healthy; then
  echo "Update to $NEW is live."
else
  echo "New version did not start; rolling back to $OLD." >&2
  as_owner git reset --hard --quiet "$OLD"
  install_and_restart
  healthy && echo "Rolled back to $OLD." || echo "Rollback did not start either. See: journalctl -u arah -n 80" >&2
  exit 1
fi
