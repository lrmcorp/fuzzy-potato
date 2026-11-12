#!/usr/bin/env bash
# Deploy origin/main when it has moved, and go back to the previous commit if the new one
# does not come up healthy. Run by the arah-update timer (see deploy/install-auto-update.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
UP="${ARAH_UP_CMD:-bash deploy/vps-up.sh}"

git fetch --quiet origin main
OLD="$(git rev-parse HEAD)"
NEW="$(git rev-parse origin/main)"
[ "$OLD" = "$NEW" ] && exit 0

echo "Updating ARAH $OLD -> $NEW"
# Fast-forward only: hand edits on the server stop the update instead of being overwritten.
git merge --ff-only --quiet origin/main
if $UP; then
  echo "Update to $NEW is live."
else
  echo "New version did not come up healthy; going back to $OLD." >&2
  git reset --hard --quiet "$OLD"
  $UP && echo "Back on $OLD." || echo "The previous version did not start either. See: docker compose -f deploy/compose.yaml logs arah" >&2
  exit 1
fi
