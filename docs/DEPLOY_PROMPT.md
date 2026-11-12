# Deployment prompt for the server operator

Copy the block below and hand it to the person (or AI agent) who manages the server and the GitHub
repositories. Secret values go to them through a private channel, never into a ticket or shared chat.

This is written for the LRM server (Tencent Lighthouse, `43.152.240.47`), where one Caddy container from
`lrmcorp/ln` already serves ports 80 and 443 and other apps join it on the Docker network `lnint-edge`.
For any other Linux server, use `./setup.sh` as described in the README instead.

```text
TASK
Put the ARAH app online at https://arah.lnint.xyz and make every merge to `main` deploy by itself.
When you finish: the dashboard asks for the owner's password over HTTPS, the Telegram bot answers /brief,
and a push to `main` of lrmcorp/fuzzy-potato goes live through GitHub Actions without anyone logging in
to the server.

HOW IT FITS TOGETHER
- ARAH runs as one Docker container named `arah` (service `arah`, compose project `arah`) in ~/arah on the
  server. It publishes no ports. Its data lives in the Docker volume `arah_arah_data`.
- The existing Caddy container from lrmcorp/ln reaches it as `arah:8787` over the network `lnint-edge`
  and serves https://arah.lnint.xyz. That site block lives in lrmcorp/ln (deploy/Caddyfile.domain), because
  every ln deploy replaces that file on the server.
- GitHub Actions in lrmcorp/fuzzy-potato (.github/workflows/deploy.yml) tests the code, copies the commit
  to ~/arah, writes ~/arah/.env.vps (mode 600) from repository secrets, builds and starts the container,
  waits for it to be healthy, then checks the public URL.
- DNS: the A record arah.lnint.xyz -> 43.152.240.47 is already active. Do not add an AAAA record.

VALUES YOU NEED FROM THE OWNER (never print them in logs or reports)
- ARAH_PASSWORD        dashboard password chosen by the owner, 12+ characters, no single quote
- OPENROUTER_API_KEY   from openrouter.ai/keys
- TELEGRAM_BOT_TOKEN   from @BotFather            (optional)
- TELEGRAM_CHAT_ID     the owner's numeric id     (optional)
- VPS_SSH_KEY          the same private key already stored as a secret in lrmcorp/ln

STEPS

1. Repository secrets and variable. In GitHub, open lrmcorp/fuzzy-potato > Settings > Secrets and variables
   > Actions. Under Secrets create: VPS_SSH_KEY, ARAH_PASSWORD, OPENROUTER_API_KEY, and, if the owner uses
   Telegram, TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID. Under Variables create VPS_DEPLOY_ENABLED = true.

2. Caddy site. Merge the pull request in lrmcorp/ln that adds the `arah.lnint.xyz` site to
   deploy/Caddyfile.domain. Its deploy workflow restarts Caddy. Until ARAH is running, the new site answers
   502; int.lnint.xyz and agent.lnint.xyz are not affected. Confirm the ln workflow run is green.

3. First ARAH deploy. Merge the ARAH pull request to `main` of lrmcorp/fuzzy-potato, or open Actions >
   "Deploy ARAH to the VPS" > Run workflow. Both jobs (validate, deploy) must end green.

4. Verify on the server (Tencent "Run commands" as root works; `~` is /home/ubuntu):
       docker ps --format '{{.Names}}  {{.Status}}  {{.Networks}}  {{.Ports}}' | grep -i arah
           -> one container, "healthy", network lnint-edge, no published ports
       docker exec ln-demo-caddy-1 wget -qO- http://arah:8787/api/session
           -> JSON containing "auth_required":true
       curl -sI https://arah.lnint.xyz | head -1
           -> HTTP/2 200
       ss -ltnp | grep 8787
           -> empty (the port is not open on the host)
       cat /home/ubuntu/arah/.deploy-revision
           -> the commit that GitHub shows as deployed
   Then open https://arah.lnint.xyz, sign in with the owner's password, and wait about a minute for the first
   summary. If Telegram is configured, send /brief to the bot and confirm a reply.

5. Verify automatic deployment. Make any small merge to `main` (or re-run the workflow) and confirm that
   /home/ubuntu/arah/.deploy-revision changes to the new commit and the container is healthy again.

OPERATIONS
- Logs:              cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml logs -f --tail 100 arah
- Restart:           cd /home/ubuntu/arah && docker compose -f deploy/compose.yaml restart arah
- Change a setting or the password: change the repository secret, then re-run the deploy workflow.
                     A new password signs every device out.
- Roll back:         revert the commit on `main`; the workflow deploys the previous code.
- Backup:            the Docker volume arah_arah_data (file arah.db) and /home/ubuntu/arah/.env.vps.
- Connectivity check: docker compose -f deploy/compose.yaml exec arah arah doctor

RULES
- Never commit, paste or log the contents of .env.vps or any secret.
- Do not publish port 8787 and do not remove the dashboard password.
- Do not edit files under /home/ubuntu/arah or /home/ubuntu/ln by hand: both are replaced on every deploy.
  Change the repositories instead.
- If a step fails, stop and report the exact command and its output instead of working around it.

REPORT BACK TO THE OWNER
1. Links to the two green workflow runs (ln and fuzzy-potato).
2. The output of steps 4 and 5.
3. Anything that did not match these instructions.
```

## Notes for the owner

- The container image, the GitHub Actions deploy and the Caddy site could not be run in the build
  environment (no Docker daemon, no access to the server). What was checked there: the app installed the way
  the image installs it serves the dashboard and marks the session cookie Secure behind proxy headers, the
  script that writes the server settings, and the syntax of the workflow and compose files. Ask the operator
  for the output of steps 4 and 5.
- The Claude Code fallback is not part of the container. On this server ARAH runs on OpenRouter only.
