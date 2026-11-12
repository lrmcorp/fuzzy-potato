#!/usr/bin/env bash
# Build and start ARAH on this server by hand, the same way the deploy workflow does.
# Run from the checkout:  bash deploy/vps-up.sh
# Settings are read from .env.vps; create it first with deploy/write-vps-env.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo -n"
compose() { $SUDO docker compose -f deploy/compose.yaml "$@"; }

[ -s .env.vps ] || { echo "Missing .env.vps. Create it with deploy/write-vps-env.sh first." >&2; exit 1; }
$SUDO docker network inspect lnint-edge >/dev/null 2>&1 || $SUDO docker network create lnint-edge
compose up -d --build

state=starting
for _ in $(seq 1 40); do
  state="$($SUDO docker inspect --format '{{.State.Health.Status}}' "$(compose ps -q arah)")"
  [ "$state" = healthy ] && break
  sleep 3
done
echo "container health: $state"
if [ "$state" != healthy ]; then compose logs --tail 60 arah; exit 1; fi
compose exec -T arah arah doctor || true
echo "ARAH is running as container 'arah' on lnint-edge (no published ports)."
