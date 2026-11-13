#!/usr/bin/env bash
# One-shot deploy of ARAH on the LRM server (Tencent Lighthouse, behind the Caddy container of lrmcorp/ln).
# Run as root from the checkout, with the settings on stdin:
#   bash deploy/server-deploy.sh <<'VALUES'
#   ARAH_PASSWORD=...
#   OPENROUTER_API_KEY=...
#   VALUES
# Safe to run again: it keeps existing settings, rebuilds, and repeats every check.
# It never prints a secret.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
DOMAIN="${ARAH_DOMAIN:-arah.hasseedev.com}"
SERVER_IP="${ARAH_SERVER_IP:-43.152.240.47}"
CADDY="${ARAH_CADDY_CONTAINER:-ln-demo-caddy-1}"
BLOCK="$DOMAIN {
  encode zstd gzip
  reverse_proxy arah:8787
}"

# True when the Caddyfile on stdin has a site block whose address list names $DOMAIN, alone or next to
# other names ("arah.hasseedev.com, www.example.com {"), so a shared block is never duplicated.
serves_domain() {
  awk -v d="$DOMAIN" '
    /^[^[:space:]#].*\{[[:space:]]*$/ {
      line = $0; sub(/\{[[:space:]]*$/, "", line); gsub(/,/, " ", line)
      n = split(line, a, /[[:space:]]+/)
      for (i = 1; i <= n; i++) {
        h = a[i]; sub(/^https?:\/\//, "", h); sub(/:[0-9]+$/, "", h)
        if (h == d) found = 1
      }
    }
    END { exit !found }'
}

declare -a REPORT=()
ok()   { REPORT+=("OK    $1"); echo "OK    $1"; }
warn() { REPORT+=("WARN  $1"); echo "WARN  $1" >&2; }
fail() { REPORT+=("FAIL  $1"); echo "FAIL  $1" >&2; summary; exit 1; }
step() { printf '\n== %s\n' "$1"; }
summary() {
  printf '\n==================== ARAH DEPLOY REPORT ====================\n'
  printf '%s\n' "${REPORT[@]}"
  printf 'revision: %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf '=============================================================\n'
}

step "1/7 Preflight"
[ "$(id -u)" -eq 0 ] || fail "run this as root (Tencent 'Run commands' runs as root)  [T1]"
for c in docker git curl openssl; do command -v "$c" >/dev/null || fail "missing command: $c  [T1]"; done
docker compose version >/dev/null 2>&1 || fail "docker compose plugin is missing  [T1]"
docker info >/dev/null 2>&1 || fail "the Docker daemon is not reachable  [T1]"
ok "docker $(docker version --format '{{.Server.Version}}' 2>/dev/null) with compose"
free_gb="$(df -BG --output=avail "$(docker info --format '{{.DockerRootDir}}')" | tail -1 | tr -dc 0-9)"
[ "${free_gb:-0}" -ge 4 ] || fail "only ${free_gb}G free for Docker; the build needs about 4G  [T2]"
ok "${free_gb}G free disk for Docker"
docker inspect "$CADDY" >/dev/null 2>&1 || fail "Caddy container $CADDY not found; deploy lrmcorp/ln first  [T5]"
[ "$(docker inspect -f '{{.State.Running}}' "$CADDY")" = true ] || fail "Caddy container $CADDY is not running  [T5]"
docker network inspect lnint-edge >/dev/null 2>&1 || docker network create lnint-edge >/dev/null
docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$CADDY" | grep -qw lnint-edge \
  || fail "Caddy container is not on the lnint-edge network  [T5]"
ok "Caddy container $CADDY is running on lnint-edge"
resolved="$(getent ahostsv4 "$DOMAIN" | awk '{print $1}' | sort -u | tr '\n' ' ')"
if [ "${resolved% }" = "$SERVER_IP" ]; then ok "DNS $DOMAIN -> $SERVER_IP"; else warn "DNS $DOMAIN resolves to '${resolved:-nothing}', expected $SERVER_IP  [T6]"; fi

step "2/7 Settings"
if [ ! -t 0 ]; then
  bash deploy/write-vps-env.sh || fail "settings were not written (see the message above)  [T3]"
elif [ -s .env.vps ]; then
  echo "No values given on stdin; keeping the existing .env.vps."
else
  fail "no settings: pass them on stdin as shown at the top of this script  [T3]"
fi
grep -q "^OPENROUTER_API_KEY='.\+'" .env.vps && ok "OpenRouter key set" || warn "no OpenRouter key: the AI analyst team runs on the Claude fallback only, or not at all  [T3]"
grep -q "^CLAUDE_CODE_OAUTH_TOKEN='.\+'" .env.vps && ok "Claude Code fallback token set" || echo "No Claude Code token: no fallback when OpenRouter fails (optional)."
grep -q "^ARAH_RELAY_URL='https://.\+'" .env.vps && grep -q "^ARAH_RELAY_KEY='.\{24,\}'" .env.vps \
  && ok "Cloudflare relay set for Yahoo and Stockbit" || echo "No Cloudflare relay (optional; see deploy/cloudflare/README.md)."
grep -q "^STOCKBIT_SESSION='.\+'" .env.vps && ok "Stockbit session set (realtime IDX prices)" || echo "No Stockbit session: IDX prices are about 15 minutes delayed (optional)."
grep -q "^TELEGRAM_BOT_TOKEN='.\+'" .env.vps && grep -q "^TELEGRAM_CHAT_ID='.\+'" .env.vps \
  && ok "Telegram bot configured" || echo "Telegram not configured (optional)."

step "3/7 Build and start the container (the first build takes a few minutes)"
bash deploy/vps-up.sh || fail "the container did not become healthy; its log is printed above  [T4]"
git rev-parse HEAD > .deploy-revision
ok "container arah is healthy at revision $(git rev-parse --short HEAD)"
[ -z "$(docker port "$(docker compose -f deploy/compose.yaml ps -q arah)")" ] && ok "no ports published on the host" \
  || warn "the arah container publishes a port on the host; it should not  [T4]"

step "4/7 Caddy site for $DOMAIN"
src="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$CADDY")"
[ -n "$src" ] && [ -f "$src" ] || fail "cannot find the Caddyfile mounted into $CADDY  [T5]"
echo "Caddy reads $src"
if ! serves_domain < "$src"; then
  # lrmcorp/ln main carries this exact block, so the next ln deploy keeps it.
  cp "$src" "$src.bak.$(date +%s)"
  printf '\n# ARAH by LRM dashboard, deployed separately from lrmcorp/fuzzy-potato onto the lnint-edge network.\n%s\n' "$BLOCK" >> "$src"
  echo "Added the $DOMAIN block to $src (a backup sits next to it)."
fi
if docker exec "$CADDY" cat /etc/caddy/Caddyfile 2>/dev/null | serves_domain; then
  ok "Caddy already serves $DOMAIN"
else
  envs=()
  while IFS= read -r e; do case "$e" in SITE_DOMAIN=*|AGENT_DOMAIN=*) envs+=(-e "$e");; esac; done \
    < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "$CADDY")
  docker run --rm "${envs[@]}" -v "$src:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
    caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>/tmp/arah-caddy-check.txt \
    || { cat /tmp/arah-caddy-check.txt >&2; fail "the Caddyfile does not parse; Caddy was NOT restarted  [T5]"; }
  # The file is bind-mounted and may have been replaced, so only a restart is sure to load it.
  docker restart "$CADDY" >/dev/null || fail "Caddy did not restart  [T5]"
  sleep 5
  docker exec "$CADDY" cat /etc/caddy/Caddyfile | serves_domain || fail "Caddy restarted but still lacks the $DOMAIN block  [T5]"
  ok "Caddy restarted with the $DOMAIN site"
fi

step "5/7 Checks"
docker exec "$CADDY" wget -qO- "http://arah:8787/api/session" 2>/dev/null | grep -q '"auth_required":true' \
  && ok "Caddy reaches arah:8787 and the login is on" || fail "Caddy cannot reach arah:8787 over lnint-edge  [T5]"
local_code="$(curl -sk -o /dev/null -w '%{http_code}' --max-time 20 --retry 6 --retry-delay 5 --retry-all-errors \
  --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/session" || true)"
[ "$local_code" = 200 ] && ok "HTTPS on the server answers 200" || warn "HTTPS on the server answered '$local_code'  [T6]"
public_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 --retry 12 --retry-delay 10 --retry-all-errors \
  "https://$DOMAIN/api/session" || true)"
[ "$public_code" = 200 ] && ok "https://$DOMAIN answers 200 with a valid certificate" \
  || warn "https://$DOMAIN answered '$public_code' with certificate checks on  [T6]"
docker compose -f deploy/compose.yaml exec -T arah arah doctor 2>&1 | sed 's/^/    /'
echo "Feature check (live prices, forecasts, Stockbit):"
while IFS= read -r line; do
  case "$line" in
    "OK   "*) ok "${line#OK   }" ;;
    "WARN "*) warn "${line#WARN }" ;;
    *) echo "    $line" ;;
  esac
done < <(docker compose -f deploy/compose.yaml exec -T arah arah selfcheck 2>&1)

step "6/7 Automatic updates"
bash deploy/install-auto-update.sh && ok "every 5 minutes, new commits on main are deployed (rollback if unhealthy)" \
  || warn "automatic updates were not installed  [T7]"

step "7/7 First summary"
echo "ARAH builds its first summary about a minute after start; open https://$DOMAIN and sign in with ARAH_PASSWORD."
summary
