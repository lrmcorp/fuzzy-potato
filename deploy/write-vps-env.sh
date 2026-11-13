#!/usr/bin/env bash
# Create or update ~/arah/.env.vps on the server. Run by the deploy workflow.
# Values arrive on stdin as NAME=value lines, so they never appear in a command line or a log.
# A value that is empty leaves the existing line alone; the session secret is generated once.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
touch .env.vps
chmod 600 .env.vps

set_line() {  # set_line NAME VALUE
  local tmp; tmp="$(mktemp)"
  grep -v "^$1=" .env.vps > "$tmp" || true
  # Single quotes keep Docker Compose from expanding "$" inside a value.
  printf "%s='%s'\n" "$1" "$2" >> "$tmp"
  cat "$tmp" > .env.vps
  rm -f "$tmp"
}

grep -q '^ARAH_SECRET=' .env.vps || set_line ARAH_SECRET "$(openssl rand -hex 32)"
grep -q '^ARAH_TIMEZONE=' .env.vps || set_line ARAH_TIMEZONE Asia/Jakarta

allowed=' ARAH_PASSWORD OPENROUTER_API_KEY CLAUDE_CODE_OAUTH_TOKEN STOCKBIT_SESSION TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID ARAH_LLM_PROVIDER ARAH_LLM_FALLBACK ARAH_CLAUDE_MODEL_QUICK ARAH_CLAUDE_MODEL_DEEP ARAH_CLAUDE_CALLS_DAY ARAH_BUDGET_USD_MONTH ARAH_BUDGET_USD_DAY ARAH_MODEL_QUICK ARAH_MODEL_DEEP ARAH_RELAY_URL ARAH_RELAY_KEY '
while IFS= read -r line; do
  name="${line%%=*}"; value="${line#*=}"
  name="${name#"${name%%[![:space:]]*}"}"  # lines pasted from the docs may be indented
  # "..." is the placeholder in the docs: a line left that way is not a value.
  [[ "$line" == *=* && "$allowed" == *" $name "* && -n "$value" && "$value" != "..." ]] || continue
  if [[ "$value" == *"'"* ]]; then echo "$name must not contain a single quote." >&2; exit 1; fi
  set_line "$name" "$value"
done

if ! grep -q "^ARAH_PASSWORD='.\{12,\}'" .env.vps; then
  echo 'ARAH_PASSWORD is missing or shorter than 12 characters. Set the ARAH_PASSWORD repository secret.' >&2
  exit 1
fi
echo '.env.vps is ready (mode 600).'
