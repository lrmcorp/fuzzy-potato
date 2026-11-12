# Deployment prompt for the server operator

Copy everything in the block below and hand it to the person (or AI agent) who manages the server.
Fill in the five values marked `<...>` first. Secrets go to the operator through a private channel,
never into a ticket or a chat that others can read.

```text
TASK
Deploy the ARAH web app on our Linux server and make it update itself whenever the `main` branch changes.
When you finish, the dashboard must be reachable at https://arah.lnint.xyz behind a login, the Telegram
bot must answer /brief, and new commits on `main` must go live within about five minutes without anyone
logging in to the server.

WHAT ARAH IS
A single Python service (FastAPI, SQLite, no Docker, no Node at runtime) that listens on 127.0.0.1:8787.
The repository ships `setup.sh`, which installs everything, and `deploy/update.sh`, which does updates.
Repository: https://github.com/lrmcorp/fuzzy-potato  (branch: main)

VALUES YOU NEED (ask the owner; do not print them in logs or reports)
- ARAH_PASSWORD        = <dashboard password chosen by the owner, 12+ characters>
- OPENROUTER_API_KEY   = <OpenRouter key>
- TELEGRAM_BOT_TOKEN   = <token from @BotFather>
- TELEGRAM_CHAT_ID     = <the owner's numeric Telegram chat id>
- Git access           = <read-only deploy key or token, if the repository is private>

SERVER REQUIREMENTS
- Ubuntu 22.04+ or Debian 12+, 2 vCPU, 2 GB RAM, 10 GB disk, systemd, sudo.
- Python 3.11 or newer (the script installs it on Ubuntu/Debian if missing).
- Outbound HTTPS to: github.com, pypi.org, files.pythonhosted.org, query1.finance.yahoo.com,
  news.google.com, www.cnbcindonesia.com, www.bca.co.id, nfs.faireconomy.media, openrouter.ai,
  api.telegram.org.
- Inbound: ports 80 and 443 open to the internet (Caddy needs both for the certificate). Port 8787 stays closed.

STEPS

1. DNS. Create an A record `arah.lnint.xyz` pointing to this server's public IPv4 address (and an AAAA
   record if the server has public IPv6). Confirm before continuing:
       dig +short arah.lnint.xyz
   The answer must be this server's address. Do not continue until it is.

2. Firewall. Allow 80 and 443, keep SSH, and make sure 8787 is not exposed:
       sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw status
   If a cloud firewall or security group sits in front of the server, open 80 and 443 there as well.

3. Service user and code. Use a dedicated non-root user that has sudo:
       sudo adduser --disabled-password --gecos "" arah && sudo usermod -aG sudo arah
       sudo -iu arah
       git clone -b main https://github.com/lrmcorp/fuzzy-potato.git ~/arah && cd ~/arah
   If the repository is private, add a read-only deploy key for this user first
   (ssh-keygen -t ed25519, add the public key under the repository's Settings > Deploy keys, clone with the
   git@github.com:lrmcorp/fuzzy-potato.git URL). The same key is what automatic updates will use.

4. Install, configure, start. Pass the values in the environment, run the script, then unset them.
   Turn shell history off for this session first (`set +o history`) so the values are not saved:
        export ARAH_PASSWORD='...' OPENROUTER_API_KEY='...' TELEGRAM_BOT_TOKEN='...' TELEGRAM_CHAT_ID='...'
        ARAH_DOMAIN=arah.lnint.xyz ARAH_AUTO_UPDATE=1 ./setup.sh
        unset ARAH_PASSWORD OPENROUTER_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
   The script: installs Python packages into ./.venv, writes ./.env (mode 600) with the owner's dashboard
   password, installs and starts the `arah` systemd service, installs Caddy and adds an HTTPS reverse proxy
   for the domain, installs the `arah-update` timer, and runs a connectivity check.
   It is safe to run again: it keeps values that are already set.

5. Verify. Every check must pass:
       systemctl is-active arah caddy arah-update.timer          -> three lines saying "active"
       curl -s http://127.0.0.1:8787/api/session                 -> JSON with "auth_required":true
       curl -sI https://arah.lnint.xyz | head -1                 -> HTTP/2 200
       ss -ltnp | grep 8787                                      -> bound to 127.0.0.1 only
       ./.venv/bin/arah doctor                                   -> every source 200, provider "openrouter"
   Then open https://arah.lnint.xyz in a browser, log in with the owner's dashboard password,
   and wait about one minute for the first summary. Send /brief to the Telegram bot and confirm a reply.

6. Verify automatic deployment.
       systemctl list-timers arah-update.timer                   -> shows the next run within 5 minutes
       sudo systemctl start arah-update && journalctl -u arah-update -n 20 --no-pager
   With nothing new on `main` the run exits silently. After the next merge to `main`, the log must show
   "Update to <commit> is live." within about five minutes. If a new version fails to start, the script
   rolls back to the previous commit on its own and logs it; report that to the owner.

7. Optional fallback AI. Only if the owner asks for it: install Claude Code for the `arah` user
   (npm install -g @anthropic-ai/claude-code), run `claude setup-token` with the owner present, put the
   token in ~/arah/.env as CLAUDE_CODE_OAUTH_TOKEN, then `sudo systemctl restart arah`.
   Do not set ANTHROPIC_API_KEY on this server.

OPERATIONS
- Logs:                 journalctl -u arah -f        (app)      journalctl -u arah-update -n 50   (deploys)
- Restart:              sudo systemctl restart arah
- Change a setting:     edit ~/arah/.env, then restart
- Change the password:  edit ARAH_PASSWORD in ~/arah/.env, then restart. Every device is signed out and must log in again.
- Manual update:        sudo ~/arah/deploy/update.sh
- Roll back by hand:    cd ~/arah && git reset --hard <commit> && ./.venv/bin/pip install -e . && sudo systemctl restart arah
                        (also stop the timer first, or it will update again: sudo systemctl stop arah-update.timer)
- Backup:               ~/arah/data/arah.db and ~/arah/.env. Copy both off the server daily.

RULES
- Never commit, paste or log the contents of .env.
- Do not open port 8787 and do not disable the dashboard password.
- Do not edit tracked files on the server: automatic updates are fast-forward only and will stop if you do.
- If any verification step fails, stop and report the exact command and its output instead of working around it.

REPORT BACK TO THE OWNER
1. The dashboard URL. The owner already knows the password; do not send it back.
2. The output of step 5 and step 6.
3. Anything that did not match these instructions.
```

## Notes for the owner

- The HTTPS proxy (Caddy), the systemd service and the update timer could not be run in the build
  environment, which has no systemd. The script's other steps were run on a fresh clone. Ask the operator
  for the step 5 and step 6 output so you know those parts work on the real server.
- Automatic deployment follows `main`. Merging a pull request is what releases it.
