# ARAH

*Arah* means "direction". ARAH is a self-hosted web app and Telegram bot that tells one person,
in plain Bahasa Indonesia or English, where markets are heading and why:

- **Indonesia:** good or not now, and next month, with the reason and whether foreign investors are buying or selling;
- **Abroad:** the same for the US, Japan, Singapore and China, for anyone thinking of expanding;
- **Rupiah against the US dollar and the yuan (RMB):** good or not now, and next month, at BCA's bank rates;
- one sentence on what is happening in the world and a short view of what is likely next;
- **Events to watch** this week, each with the reason it matters;
- **Ask ARAH:** type any question and get a yes or no with reasons;
- **Calculator:** what a rupiah amount buys today in USD, CNY, SGD, JPY or EUR, the likely range in a month, and whether to exchange now or in parts;
- **Alerts** on Telegram when an answer changes, and a **7-day report** of how many calls were right;
- behind each answer: "Why?" opens three reasons, "See the chart" opens the forecast for any horizon from one hour to months;
- stock picks for Indonesia and the US.

"Good" is from the side of someone holding rupiah: rising stocks are good, a weaker rupiah is not.
Every answer is a yes or a no. "Next month" takes the likelier side even when the edge is thin, and states
the chance and how strong it is (thin under 55%, fair to 59%, strong from 60%).

The product requirements are in [docs/PRD.md](docs/PRD.md). The visual direction is in [DESIGN.md](DESIGN.md).

## How it reaches a conclusion

1. **Statistical model.** A filtered historical simulation produces thousands of possible price paths from
   each asset's own history. From them come the chance of a rise, the reasonable range and the chance of
   touching a level.
2. **Facts.** Trend, stretch, volatility and cross-market drivers (for USD/IDR: the dollar index, US yields,
   VIX, IHSG, oil) are turned into numbered plain-language facts.
3. **AI analyst team (optional).** Claude (through your own Claude plan) or DeepSeek (through OpenRouter) plays country desks (Indonesia,
   US, Japan, Singapore, global), a bull and a bear, and a chief strategist who gives one conclusion. The
   team may nudge the model's probability by at most 6 points, and every claim must cite a numbered fact or
   headline. Claims without a valid citation are discarded.
4. **Ledger.** Every forecast is stored and scored when its horizon passes. The Track record page shows the
   result.

## What the tests say (read this before trusting it)

The model was walk-forward tested on up to ten years of data.

- **Ranges are reliable.** The "90% range" contained the outcome roughly 85 to 96% of the time across assets.
  The chance of touching a level comes from the same paths.
- **Direction from prices alone is close to a coin flip**, as it is for almost everyone. Most "chance of a
  rise" numbers sit between 45% and 56%, and the app says "unclear" instead of pretending.
- The AI team's nudges are **not validated yet**. The ledger measures them separately from the model so
  you can see, after a few weeks, whether they help.

ARAH is a research tool. Nothing it shows is investment advice.

## Install on a Linux VPS

Needs Python 3.11 or newer. A 2 vCPU, 2 GB machine is enough. One command does everything: system
packages, install, questions for your keys, a background service that starts on boot, and a final check.

```bash
git clone https://github.com/lrmcorp/fuzzy-potato.git && cd fuzzy-potato && ./setup.sh
```

The script asks for three optional things and skips any you leave empty: an OpenRouter API key
(openrouter.ai/keys), a Telegram bot token (@BotFather) and your Telegram chat id (@userinfobot). It prints
the dashboard password at the end. Run it again any time; it keeps what is already set.

Settings live in `.env`:

| Variable | What it does |
|---|---|
| `ARAH_PASSWORD` | Dashboard password (generated for you). |
| `ARAH_LLM_PROVIDER` | Main provider for the AI analyst team: `openrouter` (default) or `claude`. The other one is the fallback when it is set up. |
| `ARAH_LLM_FALLBACK` | `on` (default) or `off`. Off means only the main provider is used. |
| `CLAUDE_CODE_OAUTH_TOKEN` | For `claude`: the token printed by `claude setup-token`. |
| `ARAH_CLAUDE_MODEL_QUICK`, `ARAH_CLAUDE_MODEL_DEEP`, `ARAH_CLAUDE_CALLS_DAY` | Claude models (default `haiku` and `sonnet`) and a daily call cap (default 150). |
| `OPENROUTER_API_KEY` | Key for OpenRouter. Without any provider ARAH runs on the model and facts only. |
| `ARAH_MODEL_QUICK`, `ARAH_MODEL_DEEP` | OpenRouter model ids. Defaults are DeepSeek models. |
| `ARAH_BUDGET_USD_MONTH`, `ARAH_BUDGET_USD_DAY` | Spending caps. Past the cap the team is skipped. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Bot token from @BotFather and your own chat id. Only that chat is answered. |

ARAH listens on `127.0.0.1:8787` only. Reach it from your own computer through an SSH tunnel:

```bash
ssh -L 8787:127.0.0.1:8787 user@your-vps
```

Then open `http://127.0.0.1:8787`. After editing `.env`, run `sudo systemctl restart arah`.

## Claude Code as the fallback (or the main provider)

By default the team runs on DeepSeek through OpenRouter. When OpenRouter refuses a call (no credit, bad key,
budget cap reached, or an outage), ARAH finishes that call on the Claude Code CLI, signed in with your own
Claude plan, and skips OpenRouter for the next 30 minutes. Set `ARAH_LLM_PROVIDER=claude` to reverse the order. One brief is 8 calls
(5 desks, a bull, a bear, the chief), and took about 96 seconds in testing.

```bash
npm install -g @anthropic-ai/claude-code
```

```bash
claude setup-token
```

Put the printed token in `.env` as `CLAUDE_CODE_OAUTH_TOKEN` and restart. `arah doctor` shows the main provider and the fallback.

- Calls draw on the same plan quota as your own use of Claude. `ARAH_CLAUDE_CALLS_DAY` caps them.
- Do not set `ANTHROPIC_API_KEY` on the VPS: the CLI would bill that key instead of the plan. ARAH also
  removes it from the CLI's environment.
- The CLI gets no tools. It can read the prompt and answer, nothing else.
- This is for your own use with your own plan. Anthropic does not allow offering Claude plan login to
  other people through an app, so if ARAH is ever shared, switch to an API key provider.

## Commands

| Command | What it does |
|---|---|
| `arah up` | Dashboard, scheduler and Telegram bot. |
| `arah brief` | Build a brief now and print it. |
| `arah forecast USDIDR 2w` | Forecast one asset. Horizons: `1h 4h 1d 1w 2w 3w 1m` or free-form like `6h`, `3d`, `5w`. |
| `arah recs id` / `arah recs us` | Stock picks. |
| `arah validate` | Re-run the historical test. |
| `arah doctor` | Check configuration and connectivity. |

Telegram: `/brief`, `/tanya <question>` (or just type the question), `/hitung 100000000 USD`, `/rapor`, `/arah USD 1w`,
`/analisa BBCA`, `/rek id`, `/alert USDIDR > 18500`, `/alerts`, `/lang en`.

Briefs go out at 07:30, 12:00, 16:30, 20:00 and 05:00 WIB, plus a weekly outlook on Sunday 19:00.

## Data and its limits

- Prices come from Yahoo Finance and are delayed by about 10 to 15 minutes for IDX.
- Currency rates shown on the summary and used by the calculator are BCA's e-Rate from bca.co.id. The direction and
  range are still computed from market history and re-based onto the BCA rate.
- The event calendar covers the current week only. Indonesian events appear only when a headline states the date.
- Foreign flow comes from market-wrap headlines, refreshed with every brief. The Indonesia desk picks the newest
  full-day figure, states its date, links the source, and says so when two reports for the same day disagree
  (outlets differ on regular market versus all markets). No free machine-readable source was found: idx.co.id
  refuses automated access, and Sectors (sectors.app) offers a per-stock foreign-flow API that needs an API key.
- Coal and nickel have no free futures feed and are left out.
- Yahoo's CNY/IDR series is broken, so the yuan rate is computed from USD/IDR and USD/CNY.
- News comes from CNBC Indonesia and Google News RSS. Forum and social sentiment is not included yet.

## Not built yet

Against the PRD: the Kronos model, the `idx` data layer (per-stock foreign flow, bandarmology), paper trading,
forum sentiment and the Japan/Singapore stock lists are still to come. See the status table at the end of
the PRD.

## Development

```bash
.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest
```

```bash
cd web && npm install && npm run build
```

The web build writes to `arah/static`, which is committed so a VPS does not need Node.

## Credits

Ideas and structure draw on the projects listed in the PRD references: TradingAgents (multi-agent debate),
Vibe-Trading (skills and desks), idx and Pulse-CLI (Indonesian market conventions), Kronos and freqtrade
(evaluation discipline). The interface uses the [Astryx](https://github.com/meta/astryx) design system and
follows the [anti-slop](https://github.com/miqdadbadjuber/anti-slop) rules. No code from those projects is
copied into this repository.
