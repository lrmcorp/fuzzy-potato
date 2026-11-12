# ARAH

*Arah* means "direction". ARAH is a self-hosted web app and Telegram bot that tells one person,
in plain Bahasa Indonesia or English, where markets are heading and why:

- where the world is heading today (risk-on, risk-off or mixed);
- USD/IDR and other currencies over the next hour, 4 hours, day, 1 to 3 weeks and month, or any horizon you type;
- IHSG, Indonesian and US stocks, gold, oil, palm oil, copper, Bitcoin;
- the reasons behind each conclusion, as a short list of points;
- stock picks for Indonesia and the US, each with three strengths, why it is still worth entering, risks and a plan;
- a watch level for the rupiah (Aman, Waspada, Siaga, Bahaya) and the chance of touching levels such as 18,500.

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

Needs Python 3.11 or newer. A 2 vCPU, 2 GB machine is enough.

```bash
git clone https://github.com/lrmcorp/fuzzy-potato.git
```

```bash
cd fuzzy-potato && ./install.sh
```

The installer creates `.venv`, installs ARAH and writes `.env` with a generated dashboard password.
Then edit `.env`:

| Variable | What it does |
|---|---|
| `ARAH_PASSWORD` | Dashboard password (generated for you). |
| `ARAH_LLM_PROVIDER` | `openrouter`, `claude` or `auto`. Picks what the AI analyst team runs on. |
| `CLAUDE_CODE_OAUTH_TOKEN` | For `claude`: the token printed by `claude setup-token`. |
| `ARAH_CLAUDE_MODEL_QUICK`, `ARAH_CLAUDE_MODEL_DEEP`, `ARAH_CLAUDE_CALLS_DAY` | Claude models (default `haiku` and `sonnet`) and a daily call cap (default 150). |
| `OPENROUTER_API_KEY` | For `openrouter`, and the fallback when Claude is unavailable. Without any provider ARAH runs on the model and facts only. |
| `ARAH_MODEL_QUICK`, `ARAH_MODEL_DEEP` | OpenRouter model ids. Defaults are DeepSeek models. |
| `ARAH_BUDGET_USD_MONTH`, `ARAH_BUDGET_USD_DAY` | Spending caps. Past the cap the team is skipped. |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Bot token from @BotFather and your own chat id. Only that chat is answered. |

Start it:

```bash
.venv/bin/arah up
```

ARAH listens on `127.0.0.1:8787` only. Reach it from your own computer through an SSH tunnel:

```bash
ssh -L 8787:127.0.0.1:8787 user@your-vps
```

Then open `http://127.0.0.1:8787`. To keep ARAH running after logout, use `deploy/arah.service`.

## Running the analyst team on your Claude plan

ARAH can call the Claude Code CLI in print mode instead of OpenRouter. One brief is 8 calls
(5 desks, a bull, a bear, the chief), and took about 96 seconds in testing.

```bash
npm install -g @anthropic-ai/claude-code
```

```bash
claude setup-token
```

Put the printed token in `.env` as `CLAUDE_CODE_OAUTH_TOKEN`, set `ARAH_LLM_PROVIDER=claude`, and restart.

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

Telegram: `/brief`, `/arah USD 1w`, `/analisa BBCA`, `/rek id`, `/alert USDIDR > 18500`, `/alerts`, `/lang en`.

Briefs go out at 07:30, 12:00, 16:30, 20:00 and 05:00 WIB, plus a weekly outlook on Sunday 19:00.

## Data and its limits

- Prices come from Yahoo Finance and are delayed by about 10 to 15 minutes for IDX.
- Hourly USD/IDR quotes from this source often stand still outside Jakarta hours. ARAH flags hour-level
  rupiah forecasts as less reliable.
- Yahoo's currency series contain bad ticks, sometimes for several days. ARAH filters jumps that snap
  straight back. Without that filter the rupiah watch level was badly overstated during testing.
- Coal and nickel have no free futures feed and are left out.
- News comes from CNBC Indonesia and Google News RSS. Forum and social sentiment is not included yet.

## Not built yet

Against the PRD: the Kronos model, the `idx` data layer (foreign flow, bandarmology), paper trading,
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
