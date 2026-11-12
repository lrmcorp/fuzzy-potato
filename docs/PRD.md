# PRD — ARAH: AI Research & Analysis Hub for Markets

| | |
|---|---|
| **Document** | Product Requirements Document (PRD) |
| **Product (working name)** | **ARAH** — *"arah"* = "direction" in Bahasa Indonesia |
| **Version** | 0.4 (v0.1 of the app built; see §19 for what is done and what is not) |
| **Date** | 2026-11-12 |
| **Owner** | Single owner / single user |
| **Status** | App v0.1 implemented and tested; remaining scope listed in §19 |
| **Language** | PRD in English; the application is bilingual (Bahasa Indonesia / English) |

---

## 0. Decisions already made (from the owner Q&A)

| Topic | Decision |
|---|---|
| LLM | **DeepSeek models via OpenRouter** for all agents (decided in v0.2; no self-hosted LLM at launch). The LLM layer stays provider-agnostic (OpenAI-compatible API), so switching to another OpenRouter model or adding a local LLM later is only a config change. |
| Hardware | **No large VPS required.** Develop on the owner's own laptop/PC first, then move to a small VPS (2–4 vCPU, 4–8 GB RAM) so briefs and alerts run 24/7. |
| Market & news data | Start with free sources; **paid sources are optional and the PRD must state their budget** (see §11). |
| Execution | **Analysis + paper trading only.** No live orders with real money. |
| Asset coverage | **Indonesian stocks (IDX)**, **US stocks**, **FX (currencies)**, **crypto & commodities**. |
| Delivery channels | **Telegram bot** + **web dashboard** (plus the terminal CLI). |
| VPS | Not yet purchased — **the PRD recommends the specs and costs** (see §10). |
| Users | **Single-user** (owner only). |
| Language | PRD in English; **app is bilingual ID/EN**. |

---

## 1. Summary

ARAH is a self-hosted web application, installed and controlled from the terminal on the owner's VPS. It produces **daily market intelligence** and **horizon forecasts** for:

1. **Global FX:** e.g. USD/IDR, JPY/IDR, SGD/IDR, DXY. Includes level alerts such as "will USD/IDR reach 18,500?"
2. **The Indonesian stock market:** IHSG, sectors and individual stocks.
3. **US stocks**, plus Japan and Singapore as selectable country desks.
4. **Crypto and the commodities that drive IDX:** coal, CPO, nickel, gold, oil.

The analysis comes from a **team of specialised AI agents**: analysts, bull and bear researchers, trader personas, a risk team, a portfolio manager and **political/geopolitical desks for Indonesia, the US, Japan and Singapore**. Their work is grounded in market data, fundamentals, news, political news and forum/social sentiment. A **quantitative forecasting engine** (the Kronos foundation model plus statistical baselines) supports the agents. The output is **one clear conclusion** per asset and horizon: direction, probability, expected range and confidence, together with the reasons.

The owner chooses the forecast **interval/horizon**: 1 hour, 4 hours, 1 day, 1 week, 2 weeks, 3 weeks, 1 month or a custom value. Results go to the **Telegram bot** and the **web dashboard** as soon as each analysis finishes.

> **Honesty principle (non-negotiable).** Markets cannot be predicted with certainty. ARAH states **probabilities, not promises**. It measures and displays its own track record for every forecast, and it never claims accuracy that it has not shown in out-of-sample tests. The "experienced trader" agents are **personas encoded as prompts and methodologies**; they are not real people and carry no real track record. This disclaimer appears in the UI.

---

## 2. Goals & Non-Goals

### 2.1 Goals
- **G1 — Daily briefing:** an automatic morning brief (pre-IDX-open) and an evening brief (post-IDX-close and pre-US-open), covering FX, IHSG, the US market, commodities, crypto and politics.
- **G2 — Multi-horizon forecasts:** direction + probability + price range for any supported asset over the horizons the owner chooses.
- **G3 — Stock recommendations (ID & US):** each pick shows **3 key strengths (keunggulan) as bullet points**, **"why this stock is still worth entering now"**, key risks, an entry/target/stop plan, the horizon and a confidence level.
- **G4 — FX vigilance (kewaspadaan):** a 4-level alert scale (*Aman / Waspada / Siaga / Bahaya*) with the probability of touching user-defined levels (e.g. USD/IDR 18,500) within a horizon, and the drivers behind it.
- **G5 — Political intelligence:** country desks for Indonesia, US, Japan and Singapore (extensible) that turn political and policy news into market-impact assessments.
- **G6 — One conclusion:** every analysis ends in a single synthesised verdict. It is not left as a pile of conflicting reports.
- **G7 — Push delivery:** results are pushed to Telegram and the dashboard as soon as they are ready, and alerts fire when thresholds are crossed.
- **G8 — Accountability:** every forecast is logged and scored automatically afterwards. Hit rate, calibration and error versus a naive baseline are visible.
- **G9 — Paper trading:** simulate the recommendations with Indonesian and US market rules to measure their real usefulness.
- **G10 — Terminal-installable:** one install command and one `arah up` to run the whole stack on the VPS.

### 2.2 Non-Goals (v1)
- Live order execution with real money (possible later; out of scope now).
- Multi-user, SaaS or selling signals to others. That would raise **OJK licensing** issues.
- High-frequency or tick-level trading.
- Guaranteeing any return or accuracy level.
- Options and derivatives analytics for IDX, where liquidity is insufficient.

---

## 3. User & Use Cases

**Persona:** an Indonesian investor and trader who holds IDX and US equities and cares about the rupiah's direction. They want an AI research team that briefs them every day and that they can query at any time.

| # | User story | Priority |
|---|---|---|
| U1 | At 07:30 WIB I get a Telegram brief: overnight global moves, USD/IDR outlook, IHSG outlook, top political events and today's watchlist. | P0 |
| U2 | I type `/fx USDIDR 2w` and get the direction, probability, range, the probability of touching 18,500 and the drivers. | P0 |
| U3 | I type `/forecast BBCA 1w` (or ask in natural language, "BBCA seminggu ke depan gimana?") and get one conclusion with its reasons. | P0 |
| U4 | I open the dashboard and see recommended stocks for **Indonesia** and the **US**, each with 3 strengths, a "why still enter" note, risks and a plan. | P0 |
| U5 | I choose the horizon (1h, 1w, 2w, 3w, 1m or custom) and the countries (ID, US, JP, SG) in the UI. | P0 |
| U6 | I set alerts ("USD/IDR > 18,500", "BBRI < 3,800", "BI rate decision") and receive them on Telegram. | P0 |
| U7 | I read the full agent debate (bull vs bear, risk team) behind a verdict. | P1 |
| U8 | I see the track record: how accurate past forecasts were, by horizon and asset class. | P1 |
| U9 | I paper-trade the recommendations and see P&L with IDX fees, lots and ARA/ARB limits. | P1 |
| U10 | I switch the language (ID/EN) and the LLM provider (cloud or local) from settings. | P1 |

---

## 4. Reference Repository Assessment — "keep the best, drop the rest"

Each repository was cloned and reviewed (commit hashes in §17). The table below records **what ARAH adopts, what it adapts and what it drops**, with the reasons.

### 4.1 TradingAgents (TauricResearch) — Apache-2.0
| Verdict | Item | Reason |
|---|---|---|
| ✅ **Adopt (core)** | Multi-agent LangGraph architecture: Analyst team → Bull/Bear researcher debate → Research Manager → Trader → Risk team (aggressive/conservative/neutral) → Portfolio Manager | Best-designed "trading firm" agent pipeline among the references; it is the backbone of G6 (one conclusion). |
| ✅ Adopt | Five-tier rating scale (Buy / Overweight / Hold / Underweight / Sell) and its deterministic rating parser | Gives a consistent, machine-readable verdict. |
| ✅ Adopt | Quick-think vs deep-think model tiers, each with its own provider | Lets the cheaper DeepSeek chat model do bulk work while the DeepSeek reasoning model makes the final decision. Controls cost. |
| ✅ Adopt | Multi-provider registry incl. Ollama and `openai_compatible` (vLLM, llama.cpp) | Lets ARAH call DeepSeek through OpenRouter today and keeps the option of a local model later. |
| ✅ Adopt | Point-in-time integrity (no look-ahead), decision log memory, checkpoint resume, structured outputs | Essential for honest backtests (G8). |
| ✅ Adopt | Vendors: FRED (macro), SEC EDGAR (US fundamentals), Reddit, StockTwits, Polymarket (event probabilities) | Good US and global coverage. |
| ⚠️ Adapt | Sentiment, News, Fundamentals and Market analysts | Add Indonesian sources and Bahasa Indonesia news understanding. |
| ❌ Drop | Built-in CLI UI | Replaced by ARAH's own CLI, web UI and Telegram. |

### 4.2 Vibe-Trading (HKUDS) — MIT (with NOTICE)
| Verdict | Item | Reason |
|---|---|---|
| ✅ **Adopt (core)** | **Skill library pattern** (`SKILL.md` per skill, ~90 skills) | Gives a modular "skills" layer that agents load as needed. |
| ✅ Adopt (skills) | `geopolitical-risk`, `global-macro`, `macro-analysis`, `sentiment-analysis`, `social-media-intelligence`, `technical-basic`, `candlestick`, `ichimoku`, `smc`, `volatility`, `risk-analysis`, `valuation-model`, `financial-statement`, `fundamental-filter`, `dividend-analysis`, `earnings-revision`, `sector-rotation`, `commodity-analysis`, `correlation-regime`, `event-driven`, `corporate-events`, `behavioral-finance`, `thesis-tracker`, `research-discipline`, `report-generate`, `multi-factor`, `quant-statistics`, `yfinance`, `ccxt`, `onchain-analysis`, `stablecoin-flow`, `us-etf-flow`, `edgar-sec-filings` | Relevant to IDX, US, FX, commodities and crypto. |
| ✅ Adopt | **Swarm team presets** as templates: `geopolitical_war_room`, `macro_rates_fx_desk`, `investment_committee`, `global_equities_desk`, `sentiment_intelligence_team`, `risk_committee`, `commodity_research_team`, `sector_rotation_team` | These map directly to ARAH's desks (§6). |
| ✅ Adopt | Paper-trading ledger (cash, fills, NAV, reconciliation), run cards with data provenance, versioned research artifacts with evidence, **scheduled briefs → Telegram** | Covers G7, G8 and G9. |
| ✅ Adopt | Data-source **smart fallback chain** (auto source by symbol) | Resilience when a free source breaks. |
| ❌ Drop | China-specific skills and loaders: `akshare`, `tushare`, `eastmoney`, `mootdx`, `ashare-*`, `hk-connect-flow`, `adr-hshare`, `chanlun`, `convertible-bond`, Gildata | Not relevant to ID/US/JP/SG. |
| ❌ Drop | `options-advanced`, `options-payoff`, `options-strategy`, `perp-funding-basis`, `liquidation-heatmap`, `defi-yield`, `token-unlock-treasury` (v1) | Out of scope / low value for the owner's goals. |
| ❌ Drop | `pine-script`, `vnpy-export`, Pixel Office, live broker connectors | Not needed (no live trading; own UI). |
| ❌ Drop | `elliott-wave`, `harmonic` | Too subjective, weak evidence, and they add noise to the verdict. |

### 4.3 idx (fzn0x) — MIT, Rust single binary
| Verdict | Item | Reason |
|---|---|---|
| ✅ **Adopt (core IDX data)** | Use the `idx` binary **as a subprocess / MCP server** (47 typed tools, stable JSON envelope, schemas) | The most complete free IDX data layer. Its JSON and MCP interface plugs straight into agents. No code vendoring is needed. |
| ✅ Adopt | Quotes, history, intraday, fundamentals (growth/valuation/risk lenses), technicals, screener (~950 tickers), **foreign flow**, **broker summary**, **bandarmology** (`bandar detect/screen`), KSEI **ownership** register, corporate-action calendar, IDX holidays, Kontan / CNBC Indonesia news, lexicon sentiment | Indonesia-specific signals no other repository has. |
| ✅ Adopt (pattern) | `Provider` trait with fallbacks, per-endpoint cache TTLs, `--offline` mode | Resilience pattern, mirrored in ARAH's data layer. |
| ⚠️ Opt-in | Stockbit session (real-time bars, order book, insider movements) | Uses the owner's own login. Possible **ToS risk**, so it is off by default and the owner must accept it explicitly. |
| ❌ Drop | `market astro` (astrology, weton, shio) | Not an evidence-based signal. Excluded from all verdicts. |

### 4.4 Pulse-CLI (sukirman1901) — MIT, alpha
| Verdict | Item | Reason |
|---|---|---|
| ✅ Adopt (ideas) | **Trading plan generator**: entry / TP / SL / risk-reward / position sizing | Feeds the recommendation card (G3). |
| ✅ Adopt (ideas) | **Bandarmology broker profiles** (e.g. flags for brokers often linked to "gorengan" pump-and-dump) and accumulation-phase labels | A useful IDX-specific risk flag. It is merged with idx's bandarmology. |
| ⚠️ Adapt | **SAPTA** pre-markup detector (absorption, compression, BB squeeze, anti-distribution, time projection + ML) | Kept as a *candidate signal* only after it passes ARAH's walk-forward validation. Its Elliott module is dropped. |
| ⚠️ Adapt | Natural-language Bahasa Indonesia commands ("analisa BBCA", "cek pre-markup ANTM") | Pattern reused in the Telegram bot and chat. |
| ❌ Drop | Prophet-based price forecast as the primary model | Superseded by Kronos + statistical ensemble. Prophet is kept only as an optional baseline. |
| ❌ Drop | Duplicated yfinance and Stockbit data code, TUI | Replaced by the idx binary and ARAH's own UI. |

### 4.5 Kronos (shiyu-coder) — MIT, AAAI 2026
| Verdict | Item | Reason |
|---|---|---|
| ✅ **Adopt (core forecasting)** | Kronos foundation model for OHLCV K-lines (pre-trained on 45+ exchanges); `KronosPredictor.predict` / `predict_batch` | State-of-the-art open model for candlestick forecasting. Its **probabilistic sampling** (`T`, `top_p`, `sample_count`) produces many future paths, from which ARAH derives direction probabilities, ranges and the probability of touching a level such as 18,500. |
| ✅ Adopt | Kronos-small (24.7M) / Kronos-base (102.3M); Kronos-mini (4.1M, 2k context) for long intraday context | Small enough for CPU or a modest GPU. |
| ✅ Adopt | Fine-tuning pipeline | Phase 2: fine-tune on IDX daily data and USD/IDR history. |
| ❌ Drop | Kronos-large | Not open-source. |
| ❌ Drop | Qlib A-share demo pipeline | China-specific example. |

### 4.6 freqtrade — GPL-3.0
| Verdict | Item | Reason |
|---|---|---|
| ✅ Adopt (concepts only) | Dry-run discipline, **lookahead-analysis / recursive-analysis** checks, hyperopt-style parameter search, Telegram command design, SQLite trade persistence, fiat P&L display | Battle-tested ideas for evaluation and bot UX. |
| ⚠️ Optional sidecar | Run freqtrade **unmodified as a separate process** in dry-run mode for crypto paper trading, controlled via its REST API | Keeps a process boundary, so ARAH's code is not bound by GPL-3.0. |
| ❌ Drop | Vendoring or copying freqtrade source into ARAH | **GPL-3.0 is copyleft.** Copying code would force ARAH under GPL. Also, freqtrade is crypto-only and cannot trade IDX or US stocks. |
| ❌ Drop | Live exchange trading, leverage/futures | Out of scope (paper only). |

### 4.7 Gaps none of the references cover (ARAH must build)
- **FX-specific desk:** USD/IDR drivers (BI rate, the Fed, DXY, the US 10-year yield, the trade balance, foreign bond flows, Bank Indonesia JISDOR fixing, intervention behaviour).
- **Indonesian political desk:** policy, cabinet, fiscal and APBN, BUMN/Danantara, regulation (OJK, IDX), elections and regional politics, in Bahasa Indonesia sources.
- **Country desks for Japan and Singapore:** BOJ/MAS policy, JPY/SGD, Nikkei/STI.
- **Indonesian forum and social sentiment:** Stockbit Stream (opt-in), Reddit r/finansial, X/Twitter (optional, paid).
- **Recommendation card format** with exactly 3 strengths and a "why still enter" section.
- **A forecast ledger and calibration scoring** across *all* asset classes and horizons.

---

## 5. Functional Requirements

### 5.1 Market Coverage & Universe
- **FR-1.1** IDX: all ~950 listed tickers (via `idx`), plus IHSG, LQ45, IDX30, IDX80 and sector indices.
- **FR-1.2** US: S&P 500 + NASDAQ-100 constituents by default, plus any Yahoo-supported ticker on request.
- **FR-1.3** FX: USD/IDR, EUR/IDR, JPY/IDR, SGD/IDR, CNY/IDR, AUD/IDR, DXY, USD/JPY, USD/SGD. The pair list is configurable.
- **FR-1.4** Commodities: coal (Newcastle), CPO, nickel (LME), gold, Brent/WTI oil, tin, copper.
- **FR-1.5** Crypto: BTC, ETH, plus a configurable watchlist (via ccxt / Yahoo).
- **FR-1.6** Country desks: **Indonesia, US, Japan, Singapore** at launch. Each country is a config entry (index, currency, central bank, news sources, political sources), so more countries can be added without code changes.

### 5.2 Data Ingestion
- **FR-2.1** A pluggable `Provider` interface with an ordered **fallback chain** per asset class (idx/Vibe pattern), per-endpoint caching, and an offline mode.
- **FR-2.2** Market data: OHLCV (1m to 1mo), quotes, fundamentals, corporate actions, foreign flow, broker summary and ownership for IDX.
- **FR-2.3** Macro: FRED (Fed funds, US 10Y, CPI, payrolls), Bank Indonesia (BI-Rate, JISDOR, reserves), BPS (inflation, GDP, trade balance), BOJ and MAS releases, plus an economic calendar.
- **FR-2.4** News: Indonesian sources (Kontan, CNBC Indonesia, Bisnis, Kompas, Antara), global sources (Reuters/AP via RSS where permitted, Yahoo Finance, Finnhub/Marketaux) and GDELT for global political events.
- **FR-2.5** Forums and social: Reddit, StockTwits (US), Stockbit Stream (opt-in), X/Twitter (optional, paid) and Polymarket event probabilities.
- **FR-2.6** Every datum is stored with its **source, fetch time and publish time** (point-in-time). Agents may only see data published before the analysis timestamp.
- **FR-2.7** Data-health monitor: stale or broken sources are flagged in the UI and in the report ("USD/IDR data is 3h stale").

### 5.3 Forecasting Engine (quant layer)
- **FR-3.1** User-selectable horizons: **1h, 4h, 1d, 1w, 2w, 3w, 1m and custom**. Horizons below 1d require intraday data and are flagged *low-confidence* when the source is delayed (e.g. Yahoo's ~10–15 min IDX delay).
- **FR-3.2** Ensemble forecaster:
  - **Kronos** probabilistic paths (N = 50–200 samples) produce a distribution of future closes.
  - **Statistical baselines:** random walk (naive), ARIMA/ETS, GARCH volatility and optionally Prophet.
  - **Regime and technical features** (trend, momentum, volatility regime, correlation regime).
- **FR-3.3** Outputs per asset × horizon: **direction (Up/Down/Sideways) with probabilities**, median target, 50% and 90% ranges, and the **probability of touching user levels** (e.g. P(USD/IDR ≥ 18,500 within 2w)).
- **FR-3.4** Every forecast is written to the **Forecast Ledger** and scored automatically when its horizon ends: hit rate, Brier score/calibration, MAPE and skill versus the random walk.
- **FR-3.5** A model is labelled **"validated"** only after it beats the naive baseline in walk-forward, out-of-sample tests for that asset class and horizon. Otherwise the UI labels it **"experimental"**.
- **FR-3.6** Phase 2: fine-tune Kronos on IDX daily bars and IDR FX history. The fine-tuned model must beat the base model out-of-sample before it is promoted.

### 5.4 Agent Team (LLM layer)
Defined in detail in §6.
- **FR-4.1** LangGraph orchestration with parallel analysts, a bull/bear debate (configurable rounds), a risk debate and a final Portfolio Manager decision (TradingAgents pattern).
- **FR-4.2** Agents load **skills** (SKILL.md files) on demand (Vibe-Trading pattern), from a curated ARAH skill set (§7).
- **FR-4.3** Agents call tools for data (idx MCP, data providers, Forecast Engine). **No unsourced numbers:** every figure in a report must trace to a tool call.
- **FR-4.4** Final output = **one Chief Strategist verdict** per request: rating (5-tier), direction + probability per horizon, key drivers, key risks and what would change the view (invalidation).
- **FR-4.5** Selectable research depth: *Quick* (single pass, quick-tier DeepSeek model), *Standard* (1 debate round) and *Deep* (2–3 rounds, deep-think cloud model).
- **FR-4.6** Each agent's full report and the debate transcript are stored and viewable (U7).

### 5.5 Recommendations (Indonesia & US)
- **FR-5.1** Daily screening pipeline: a quant screen (liquidity, fundamentals, momentum, foreign flow, bandarmology) produces a shortlist. The agent team then reviews it and the top N picks per market are published (default: 5 ID, 5 US).
- **FR-5.2** **Recommendation card** (required fields):
  - Ticker, name, sector, current price, rating, horizon.
  - **3 Key Strengths (3 keunggulan)**, exactly three bullet points, each grounded in data.
  - **Why it is still worth entering now (kenapa masih layak masuk)**: catalyst, valuation gap, flow and timing.
  - **Key risks** (at least 2) and the **invalidation level**.
  - **Trading plan:** entry zone, target(s), stop-loss, risk/reward and suggested position size, with lot rounding for IDX.
  - Forecast summary (direction probability per horizon) and confidence.
  - IDX-specific flags: bandar accumulation/distribution, foreign net flow, "gorengan" broker warning, UMA/suspension history.
- **FR-5.3** Filters: market, sector, style (value/growth/dividend/momentum), horizon and risk level.
- **FR-5.4** Each recommendation is tracked in the ledger and in paper trading, so its performance is visible.

### 5.6 FX Monitor & Vigilance Alerts
- **FR-6.1** An FX dashboard per pair: spot, forecasts per horizon, the probability of touching levels, drivers and the vigilance level.
- **FR-6.2** **Vigilance scale (Tingkat Kewaspadaan):**

  | Level | Meaning (example rule, configurable) |
  |---|---|
  | 🟢 **Aman** | P(touch level) < 20% and volatility is normal |
  | 🟡 **Waspada** | 20–40%, or volatility is above its 1-year 75th percentile |
  | 🟠 **Siaga** | 40–65%, or a major event is within the horizon (FOMC, BI RDG, elections) |
  | 🔴 **Bahaya** | > 65%, or the level is already breached / disorderly market |

- **FR-6.3** User-defined levels per pair (e.g. USD/IDR 17,500 / 18,000 / 18,500), each with a Telegram alert on crossing and a daily probability update.
- **FR-6.4** Each FX view gives practical implications in plain language, for example: "If you need USD within 1 month, consider staging purchases", or "IDR weakness tends to hurt importers and help exporters such as coal and CPO; see related IDX stocks". These are framed as considerations, not instructions.

### 5.7 Political & Geopolitical Desks
- **FR-7.1** A desk per country (ID, US, JP, SG; extensible) that monitors political, policy, regulatory and central-bank news.
- **FR-7.2** An event register: each event gets type, country, date, a market-impact assessment (assets, direction, magnitude, confidence) and its source links.
- **FR-7.3** An upcoming-events calendar (FOMC, BI RDG, BOJ, MAS, elections, budget, earnings seasons, IDX rebalancing) with a pre-event risk note.
- **FR-7.4** The Indonesia desk works natively in Bahasa Indonesia sources. Political analysis must be **neutral and non-partisan**, focused only on market impact.

### 5.8 Delivery: Telegram, Web, CLI
- **FR-8.1 Scheduled briefs (WIB, configurable):** 07:30 pre-IDX, 12:00 midday (IDX session break), 16:30 post-close, 20:00 pre-US-open and 05:00 US-close recap. Weekly outlook on Sunday at 19:00.
- **FR-8.2 Telegram bot** (single authorised chat ID only):
  `/brief`, `/fx <PAIR> <horizon>`, `/forecast <TICKER> <horizon>`, `/analyze <TICKER> [quick|standard|deep]`, `/rec id|us`, `/alert add|list|rm`, `/events [country]`, `/politics <country>`, `/paper`, `/track`, `/lang id|en`, `/model`. Free text in Bahasa Indonesia or English is also accepted.
- **FR-8.3** **Push on completion:** when any analysis job finishes, it is pushed to Telegram and to the dashboard via WebSocket/SSE.
- **FR-8.4 Web dashboard pages:** Home (daily brief), FX Monitor, Indonesia (IHSG, sectors, stock detail), US, Countries/Politics, Recommendations, Forecast Explorer (pick asset + horizon), Agent Room (debates), Alerts, Paper Trading, Track Record, Settings (providers, models, budget, schedules, language).
- **FR-8.5 CLI** (`arah`): `arah install`, `arah up/down/status/logs`, `arah brief`, `arah fx USDIDR 2w`, `arah forecast BBCA 1w`, `arah rec id`, `arah update`, `arah backup`.
- **FR-8.6** Bilingual: all UI strings and LLM outputs are available in ID and EN. Market terms stay in their standard form (e.g. "support", "foreign net buy").

### 5.9 Paper Trading
- **FR-9.1** A paper portfolio per market (IDR for IDX, USD for US, crypto). The owner places orders manually or enables auto-follow of recommendations.
- **FR-9.2** IDX rules: 1 lot = 100 shares, tick-size tables, **ARA/ARB** auto-rejection limits, trading sessions and holidays (from `idx`), configurable fees (default buy ≈ 0.15%, sell ≈ 0.25% incl. tax) and T+2 settlement.
- **FR-9.3** US rules: fractional shares optional, fees configurable, market hours in WIB.
- **FR-9.4** Next-bar fills (no same-bar look-ahead), slippage model, ledger reconciliation (Vibe pattern).
- **FR-9.5** Reports: equity curve, P&L, drawdown, win rate and comparison against benchmarks (IHSG, S&P 500).

### 5.10 Track Record & Evaluation
- **FR-10.1** A Forecast Ledger that is immutable once written (append-only).
- **FR-10.2** Metrics by asset class × horizon × model or agent: hit rate, Brier score, a calibration plot, MAPE, skill versus naive, and recommendation return versus benchmark.
- **FR-10.3** Weekly self-review: agents receive their own scored past decisions as memory (TradingAgents decision log) to reduce repeated mistakes.
- **FR-10.4** Backtests use point-in-time data only. Lookahead and recursive checks (freqtrade concept) run in CI.

---

## 6. Agent Team Design

```
                         ┌──────────────────────────────┐
  Scheduler / Telegram / │        ORCHESTRATOR          │
  Web / CLI request ───▶ │  (LangGraph, job queue)      │
                         └──────────────┬───────────────┘
            ┌───────────────────────────┼─────────────────────────────┐
            ▼                           ▼                             ▼
   ANALYST TEAM (parallel)     POLITICAL & MACRO DESKS        QUANT FORECAST ENGINE
   • Technical Analyst         • Indonesia Political Desk     • Kronos paths
   • Fundamental Analyst       • US Desk                      • ARIMA/ETS/GARCH
   • IDX Flow & Bandarmology   • Japan Desk                   • Regime model
   • News Analyst (ID + EN)    • Singapore Desk               • Level-touch probs
   • Sentiment & Forum Analyst • Geopolitical War Room
   • Commodity Analyst         • Global Macro & Rates/FX Desk
   • FX Analyst
            └───────────────────────────┼─────────────────────────────┘
                                        ▼
                     RESEARCH DEBATE: Bull Researcher ⇄ Bear Researcher
                                        ▼
                               Research Manager (deep-think)
                                        ▼
               TRADER DESK: "IDX Veteran Trader" persona + "Global Macro PM" persona
                                        ▼
                RISK TEAM: Aggressive ⇄ Conservative ⇄ Neutral  → Risk Manager
                                        ▼
                     PORTFOLIO MANAGER  →  CHIEF STRATEGIST (one conclusion)
                                        ▼
                     Report store → Telegram push / Dashboard / Ledger
```

| Agent | Responsibility | Key skills / tools | Model tier |
|---|---|---|---|
| Technical Analyst | Trend, momentum, S/R, patterns, volatility | technical-basic, candlestick, ichimoku, smc, volatility; `idx_technical` | quick |
| Fundamental Analyst | Valuation, growth, quality, dividends, earnings revisions | valuation-model, financial-statement, fundamental-filter, dividend-analysis, earnings-revision; `idx_fundamental`, SEC EDGAR | quick |
| IDX Flow & Bandarmology Analyst | Foreign flow, broker accumulation/distribution, ownership changes, "gorengan" flags | `idx_bandar`, `idx_foreign`, `idx_broker`, `idx_ownership_*`, Pulse broker profiles | quick |
| News Analyst | Company, sector and macro news impact (ID + EN) | event-driven, corporate-events; news providers | quick |
| Sentiment & Forum Analyst | Retail and social mood, crowding, contrarian signals | sentiment-analysis, social-media-intelligence, behavioral-finance | quick |
| Commodity Analyst | Coal, CPO, nickel, gold, oil → IDX sector impact | commodity-analysis, correlation-regime | quick |
| FX Analyst | Currency drivers, carry, flows, central-bank reaction functions | global-macro, macro-analysis; FRED, BI, JISDOR | quick → deep for FX verdicts |
| Country Political Desks (ID/US/JP/SG) | Policy, politics, regulation → market impact; neutral | geopolitical-risk, regulatory knowledge (ID-specific skill authored new) | quick |
| Geopolitical War Room | Cross-border risks (trade wars, conflicts, sanctions) | geopolitical-risk, cross-asset correlation | deep |
| Quant Forecaster (tool, not LLM) | Probabilistic forecasts and level-touch probabilities | Kronos, baselines | n/a |
| Bull / Bear Researchers | Strongest case for each side, challenging each other | research-discipline, thesis-tracker | quick |
| Research Manager | Judges the debate and writes the investment thesis | — | deep |
| Trader personas | Turn the thesis into a plan: entry/TP/SL, timing, sizing | trading plan generator, risk-analysis | quick |
| Risk Team + Risk Manager | Stress test: liquidity, volatility, event risk, concentration | risk-analysis, volatility | quick / deep |
| Portfolio Manager / Chief Strategist | Final single verdict, rating, horizon probabilities, report | report-generate | deep |

**Persona note:** "Veteran trader" agents encode documented methods (risk-first sizing, liquidity awareness, flow reading, event discipline). They do **not** claim real-world performance.

**Grounding rules:** agents must cite tool outputs; numbers without a source are rejected by a validator. Contradictions between the quant forecast and the agent verdict must be stated explicitly ("Model says 58% up; team overrides to Hold because …").

---

## 7. ARAH Skill Set (curated)

| Category | Skills (source) |
|---|---|
| Technical | technical-basic, candlestick, ichimoku, smc, volatility (Vibe); SAPTA candidate (Pulse, validation-gated) |
| Fundamental | valuation-model, financial-statement, fundamental-filter, dividend-analysis, earnings-revision, multi-factor (Vibe); idx growth/valuation/risk lenses |
| IDX-specific | bandarmology, foreign flow, broker profile flags, KSEI ownership, corporate actions, IDX calendar/holidays (idx + Pulse) |
| Macro / FX | global-macro, macro-analysis, correlation-regime (Vibe); **new:** `idr-fx-drivers`, `bi-policy-watch`, `boj-mas-watch` |
| Political | geopolitical-risk (Vibe); **new:** `indonesia-politics-policy`, `us-politics-policy`, `japan-politics-policy`, `singapore-politics-policy` |
| Sentiment | sentiment-analysis, social-media-intelligence, behavioral-finance (Vibe); idx lexicon sentiment (ID) |
| Commodities / Crypto | commodity-analysis, onchain-analysis, stablecoin-flow, ccxt (Vibe) |
| Process | research-discipline, thesis-tracker, event-driven, corporate-events, sector-rotation, risk-analysis, report-generate, quant-statistics (Vibe); trading-plan (Pulse) |
| **Excluded** | astrology (idx), elliott-wave, harmonic, chanlun, China/HK data skills, options/DeFi/perp skills, pine-script/vnpy export |

New skills are authored in the same `SKILL.md` format and versioned in the repo.

---

## 8. Output Formats (examples)

### 8.1 Stock recommendation card (ID)
```
🇮🇩 BBCA — Bank Central Asia Tbk          Rating: OVERWEIGHT   Horizon: 1 bulan
Harga: Rp 9.850   Keyakinan: Sedang (62%)

✅ 3 Keunggulan
 1. ROE 21% & NPL terendah di big-4 bank (laporan Q3)
 2. Foreign net buy 8 hari beruntun, Rp 1,2 T (IDX/IPOT)
 3. Valuasi P/B 4,1x — di bawah rata-rata 5 tahun 4,6x

🎯 Kenapa masih layak masuk
 • Katalis: pemangkasan BI-Rate diperkirakan Desember → NIM terjaga, kredit naik
 • Harga masih 6% di bawah resistance; akumulasi broker asing berlanjut

⚠️ Risiko: rupiah >18.000 memicu outflow asing; perlambatan kredit konsumer
⛔ Invalidasi: close < Rp 9.300

📋 Rencana: Entry 9.700–9.850 | TP1 10.400 | TP2 10.800 | SL 9.300 | R/R 1 : 2,1
📈 Prakiraan: 1w ↑55% · 2w ↑58% · 1m ↑61% (Kronos+ensemble, status: validated)
```
*(Numbers are illustrative only.)*

### 8.2 FX vigilance (example)
```
💱 USD/IDR  17.920   Tingkat: 🟠 SIAGA
Prakiraan 2 minggu: median 18.080 | rentang 90%: 17.650 – 18.560
P(menyentuh 18.500 dalam 2 minggu) = 31%   ·  dalam 1 bulan = 44%
Pendorong: FOMC 17 Des (hawkish risk), DXY naik, outflow SBN asing, harga batu bara turun
Desk politik: debat RAPBN-P → risiko persepsi fiskal
Implikasi: kebutuhan USD < 1 bulan → pertimbangkan beli bertahap; eksportir (ADRO, PTBA) relatif diuntungkan
```

### 8.3 Daily brief structure
1. Headline verdict (one paragraph). 2. Global overnight (US, JP, SG, commodities, crypto). 3. FX outlook + vigilance levels. 4. IHSG outlook + sector rotation. 5. Political & event calendar. 6. Top recommendations (ID/US). 7. Alerts triggered. 8. Track-record snapshot.

---

## 9. System Architecture

### 9.1 Components
| Layer | Technology (proposed) | Notes |
|---|---|---|
| Backend API | **Python 3.12, FastAPI** | REST + WebSocket/SSE for push |
| Agent orchestration | **LangGraph** (from TradingAgents) + skill loader (Vibe pattern) | Checkpointing, resume |
| LLM gateway | **OpenRouter** (OpenAI-compatible API) → **DeepSeek** models; thin router (LiteLLM or custom) so other providers / a local Ollama can be added later | Quick/deep tiers, fallback between DeepSeek models/hosts, **budget caps** |
| Forecasting service | PyTorch + **Kronos**, statsmodels / arch | Separate worker; GPU optional |
| IDX data | **`idx` binary** (Rust) via CLI JSON + MCP | Pinned version, cached |
| Other data | yfinance, FRED, SEC EDGAR, ccxt, RSS, GDELT, Reddit, StockTwits, Polymarket, optional paid APIs | Provider interface + fallback |
| Jobs & schedule | **APScheduler + Redis (arq/RQ)** | Brief schedules, data refresh, ledger scoring |
| Database | **PostgreSQL + TimescaleDB** (time series) | Ledger, reports, alerts, paper trades |
| Vector store | pgvector | News/report retrieval, agent memory |
| Frontend | **Next.js + TypeScript + Tailwind**, i18n (ID/EN), charts (TradingView Lightweight Charts / ECharts) | Responsive and mobile-friendly |
| Telegram | python-telegram-bot | Single-chat whitelist |
| Packaging | **Docker Compose**, `arah` CLI (pipx-installable, Typer) | One-command install |
| Observability | Structured logs, Prometheus + Grafana (optional), LLM cost tracking | |

### 9.2 Data flow
Scheduler → Data refresh (providers → Postgres/Timescale) → Forecast Engine (Kronos + baselines → Ledger) → Agent graph (tools read DB, idx MCP, forecast results) → Chief Strategist verdict → Report store → Push (Telegram + Web) → Ledger scoring when the horizon expires → Track Record.

### 9.3 Deployment & access
- Docker Compose on the owner's laptop (development) or one small VPS (production). Services bind to **localhost only**.
- The owner reaches the web dashboard through **Tailscale/WireGuard** or an SSH tunnel. Optionally, a reverse proxy (Caddy) with HTTPS and single-user login (password + TOTP).
- The Telegram bot uses outbound polling only, so no inbound port is needed.

### 9.4 Repository structure (proposed)
```
arah/
  backend/       # FastAPI, orchestration, providers, ledger, paper trading
  agents/        # LangGraph graphs, agent prompts (ID/EN), personas
  skills/        # SKILL.md library (curated + new)
  forecast/      # Kronos service, baselines, evaluation
  frontend/      # Next.js app (i18n)
  bot/           # Telegram bot
  cli/           # `arah` command
  deploy/        # docker-compose, Caddy, systemd
  docs/          # PRD, ADRs, runbooks
  third_party/   # LICENSE/NOTICE files of adopted components
```

---

## 10. Hardware / VPS Recommendation (owner has no VPS yet)

Because all LLM work runs on **DeepSeek via OpenRouter**, ARAH needs no GPU and no large server. Kronos-small (24.7M params) runs comfortably on CPU. Prices are **indicative (late 2026) and must be re-checked at purchase**.

| Option | Spec | Indicative cost | Notes |
|---|---|---|---|
| **1. Owner's laptop/PC (development)** | ≥ 8 GB RAM (16 GB ideal), Docker | **Free** | ✅ Start here. Briefs and alerts only run while the machine is on. |
| **2. Small VPS (production)** | 2–4 vCPU, 4–8 GB RAM, 80 GB SSD; Singapore or Jakarta region | **≈ US$5–15 / month** | ✅ Recommended once stable: 24/7 briefs and Telegram alerts. |
| 3. Home mini PC | e.g. Intel N100, 16 GB RAM | ≈ Rp 2–4 juta one-off | 24/7 without a monthly fee; depends on home power and internet. |
| 4. Oracle Cloud Always Free | ARM, up to 4 cores / 24 GB | Free | Capacity is often unavailable; card verification required; no SLA. |

**Lite mode (for 4 GB machines):** SQLite instead of Postgres/Timescale, no Redis (in-process scheduler) and Kronos-mini/small only. Selected with `arah install --lite`.

**Later (optional):** if the owner wants private, self-hosted inference, add a GPU server (≈ US$250–500/month) running Ollama/vLLM and point the router at it. No code changes are needed.

---

## 11. Budget — Paid Data & LLM (optional)

Prices are **indicative and must be verified** before subscribing. ARAH works on **Tier 0 (free)**, and each paid adapter can be switched on independently.

### 11.1 Data tiers
| Tier | What you get | Indicative cost / month |
|---|---|---|
| **Tier 0 — Free (default)** | idx (Yahoo / MSN / idx.co.id / IPOT / KSEI / Kontan / CNBC ID), yfinance (US, FX, commodities; delayed), FRED, SEC EDGAR, ECB/Frankfurter FX, BI/BPS public data, GDELT, RSS, Reddit (low volume), StockTwits, Polymarket, ccxt public crypto | **US$0** |
| **Tier 1 — Better quality (recommended upgrade)** | Real-time-ish **FX + US** data API (e.g. Twelve Data, Polygon/Massive, Finnhub paid tier: ~$30–80); news API with sentiment (Marketaux / Finnhub / Benzinga basic: ~$0–50); **IDX real-time** via the owner's Stockbit/broker account (opt-in; cost depends on the owner's subscription) or an Indonesian market-data API vendor (verify pricing) | **≈ US$50–150** |
| **Tier 2 — Pro** | X/Twitter API (≈ $200+), premium news (Reuters/Bloomberg-grade feeds are typically enterprise pricing), TradingEconomics calendar/forecasts, official IDX data feed licence | **US$300 – several thousand** |

### 11.2 LLM cost — DeepSeek via OpenRouter
Model choice (exact model IDs are set at install time from the current OpenRouter catalogue):
- **Quick tier** (analysts, researchers, debaters, trader, summaries): DeepSeek's general chat model.
- **Deep tier** (Research Manager, Portfolio Manager, Chief Strategist, FX verdicts): DeepSeek's reasoning model.

Assumptions: 5 scheduled briefs/day, ~15 analyses/day. DeepSeek is among the lowest-priced capable models, so costs are low:

| Usage profile | Indicative cost / month |
|---|---|
| Light (briefs + ~5 analyses/day) | **US$3–10** |
| Standard (as assumed above) | **US$10–30** |
| Heavy (deep mode on everything, 3 debate rounds) | **US$30–80** |

OpenRouter is prepaid credit, so spending cannot exceed the balance. **Built-in budget guard:** daily and monthly caps; above the cap, ARAH downgrades to the quick-tier model or Quick depth and notifies the owner on Telegram.

### 11.3 Total indicative monthly cost
| Setup | Total |
|---|---|
| Development (own laptop + Tier 0 data + DeepSeek) | **≈ US$5–30** |
| Recommended (small VPS + Tier 0 data + DeepSeek standard) | **≈ US$15–45** (≈ Rp 250–750 rb) |
| Upgraded data (small VPS + Tier 1 data + DeepSeek standard) | **≈ US$65–200** |

---

## 12. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 Performance | Quick analysis < 60 s, Standard < 4 min, Deep < 10 min; daily brief ready by its scheduled time (jobs start 45 min early). |
| NFR-2 Availability | Single host (laptop or small VPS); auto-restart (systemd/Docker); failed jobs retried; Telegram notice if a brief fails. |
| NFR-3 Data freshness | Every report shows each source's data timestamp; stale data is flagged. |
| NFR-4 Security | Localhost binding + VPN; single-user auth with TOTP; Telegram whitelist; secrets in `.env`/Docker secrets with `chmod 600`; no secrets in logs; dependencies pinned and scanned. |
| NFR-5 Privacy | Prompts (incl. watchlist/portfolio context) go to OpenRouter and the DeepSeek inference host. Use OpenRouter's provider-routing and data-policy settings (e.g. restrict to providers that do not train on or retain prompts); never send credentials or account identifiers in prompts; a portfolio-anonymisation option sends weights instead of absolute amounts. |
| NFR-6 Cost control | Per-provider budget caps, token accounting per job and a dashboard. |
| NFR-7 Reproducibility | Each report has a run card: model versions, prompts, data snapshot IDs and parameters. |
| NFR-8 Integrity | Point-in-time data, an append-only ledger and lookahead checks in CI. |
| NFR-9 i18n | 100% of UI strings in ID and EN; LLM output language follows the user setting. |
| NFR-10 Licensing | Respect the licences: Apache-2.0 NOTICE (TradingAgents), MIT notices (Vibe-Trading incl. its NOTICE, idx, Pulse-CLI, Kronos); **freqtrade GPL-3.0 is never vendored** (process boundary only); confirm the Kronos weight licence on Hugging Face. |
| NFR-11 Compliance | Personal use only. Every output carries a "not financial advice" disclaimer. Respect each data source's ToS. Scraping that requires login (Stockbit) is opt-in and the owner bears the responsibility. |
| NFR-12 Backup | Nightly Postgres dump + config backup (`arah backup`), with optional offsite storage. |

---

## 13. Success Metrics

| Metric | Target (after 3 months of live operation) |
|---|---|
| Brief delivery on time | ≥ 99% |
| Forecast directional hit rate (1w, IDX large caps & USD/IDR) | Beats naive/random-walk baseline with statistical significance; target **≥ 55%** |
| Calibration (Brier score) | Better than climatology baseline; calibration curve within ±10 pp |
| Recommendation performance | Paper portfolio beats IHSG / S&P 500 over rolling 3 months, risk-adjusted |
| Owner engagement | Owner reads ≥ 1 brief per trading day |
| Cost | Within the monthly budget the owner sets |

These targets are **hypotheses to validate**, not promises.

---

## 14. Release Plan / Milestones

| Phase | Scope | Duration (est.) |
|---|---|---|
| **M0 — Foundation** | Repo skeleton, Docker Compose, `arah` CLI, Postgres/Timescale, LLM gateway (OpenRouter → DeepSeek, budget guard), auth, i18n scaffolding | 1–2 weeks |
| **M1 — Data layer** | idx integration (CLI/MCP), yfinance/FRED/EDGAR/RSS/GDELT/Reddit/ccxt providers, fallback and cache, data-health monitor | 2 weeks |
| **M2 — Forecast engine** | Kronos service, baselines, level-touch probabilities, Forecast Ledger + scoring, walk-forward evaluation harness | 2–3 weeks |
| **M3 — Agent team** | LangGraph graph (analysts, debate, trader, risk, PM, chief strategist), curated skills, new ID/FX/political skills, grounding validator | 3 weeks |
| **M4 — Delivery** | Telegram bot + scheduled briefs; web dashboard (Home, FX, ID, US, Recommendations, Forecast Explorer, Agent Room, Alerts) | 3 weeks |
| **M5 — Paper trading & track record** | IDX/US/crypto paper engines, reports, track-record pages, weekly self-review | 2 weeks |
| **M6 — Hardening** | Security review, cost guard, backups, docs, VPS install runbook | 1 week |
| **Phase 2** | Kronos fine-tuning on IDX/IDR, SAPTA validation, more countries, optional Tier-1/Tier-2 data adapters, optional live-trading research | Later |

Total to v1: **about 14–16 weeks** of focused development (estimate).

---

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Forecasts are no better than chance | Misleading decisions | Ledger + baseline comparison; "experimental" label; probabilities rather than certainties; prominent disclaimer |
| LLM hallucination / invented numbers | Wrong analysis | Tool-grounding validator, sourced citations, structured outputs, low temperature for numeric tasks |
| Free data sources break or rate-limit | Gaps | Fallback chains, caching, health monitor, optional paid tiers |
| Delayed IDX data (~10–15 min) hurts 1h horizons | Lower accuracy | Flag intraday IDX forecasts low-confidence; opt-in real-time source |
| Stockbit / scraping ToS | Account ban / legal | Off by default; owner opt-in; prefer official or public sources |
| Look-ahead bias in backtests | Overstated accuracy | Point-in-time store, lookahead checks, out-of-sample holdouts |
| LLM cost overrun | Budget | Caps, downgrade to the cheaper quick-tier model, quick/deep tiering, caching of shared analyses |
| Political analysis bias | Poor or partisan output | Neutral market-impact framing, multiple sources, bull/bear debate |
| OpenRouter / DeepSeek outage or model deprecation | Analyses fail or change in quality | Retry with backoff, fallback to another DeepSeek host or model via OpenRouter routing, model IDs pinned in config, quality re-checked via the track record after any model change |
| GPL contamination (freqtrade) | Licence obligations | Concepts only; optional sidecar process; no code copying |
| Regulatory (OJK) if shared or sold | Legal | Single-user, personal use; revisit before any sharing |

---

## 16. Owner Decisions (resolved 2026-11-12 — all defaults accepted)

| # | Topic | Decision |
|---|---|---|
| 1 | Product name | **ARAH** |
| 2 | Default watchlists | **IDX:** BBCA, BBRI, BMRI, TLKM, ASII, ADRO, ANTM, GOTO + IHSG, LQ45. **US:** NVDA, AAPL, MSFT, GOOGL, AMZN + S&P 500, NASDAQ. **FX:** USD/IDR (alerts at 17,500 / 18,000 / 18,500), JPY/IDR, SGD/IDR, DXY. **Commodities:** coal, CPO, nickel, gold, oil. **Crypto:** BTC, ETH. All editable in Settings. |
| 3 | Brief schedule (WIB) | 07:30 pre-IDX · 12:00 midday · 16:30 post-close · 20:00 pre-US · 05:00 US recap · Sunday 19:00 weekly outlook |
| 4 | Monthly budget ceiling | **US$30** (LLM + data). On reaching it: downgrade to Quick depth / quick-tier model and notify via Telegram. |
| 5 | Stockbit opt-in | **No** at launch. Free data only; Stockbit adapter stays disabled (can be enabled later by the owner). |
| 6 | VPS region (production, after laptop phase) | **Singapore** |

Remaining input needed for M0: the owner's laptop/PC OS and RAM (to choose standard vs `--lite` install).

---

## 17. References

### 17.1 Source repositories (reviewed at these commits)
| Repository | Licence | Commit reviewed | What ARAH takes |
|---|---|---|---|
| [sukirman1901/Pulse-CLI](https://github.com/sukirman1901/Pulse-CLI) | MIT | `a698320` (2026-01-08), v0.1.0 | Trading-plan generator, bandarmology broker profiles, SAPTA (validation-gated), Bahasa Indonesia NL command patterns |
| [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | **GPL-3.0** | `5197bed` (2026-11-12) | Concepts only: dry-run, lookahead/recursive analysis, hyperopt, Telegram UX; optional unmodified sidecar for crypto dry-run |
| [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) | Apache-2.0 | `9fa1196` (2026-11-04) | Core multi-agent LangGraph pipeline, 5-tier ratings, quick/deep model tiers, multi-provider + Ollama, point-in-time integrity, FRED/EDGAR/Reddit/StockTwits/Polymarket vendors |
| [fzn0x/idx](https://github.com/fzn0x/idx) | MIT | `dc299f4` (2026-11-09), v0.8.2 | IDX data layer via CLI JSON / MCP (47 tools): quotes, fundamentals, technicals, screener, foreign flow, broker summary, bandarmology, KSEI ownership, calendar, news, sentiment |
| [HKUDS/Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) | MIT (+ NOTICE) | `67ce0ca` (2026-11-11), v0.1.19 | Skill library (curated subset), swarm team presets, paper-trading ledger, run cards, versioned research artifacts, scheduled briefs → Telegram, data fallback chains |
| [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos) | MIT | `67b630e` (2026-04-13) | Foundation forecasting model (Kronos-mini/small/base), probabilistic sampling, fine-tuning pipeline |

### 17.2 Papers
- Xiao, Y. et al. *TradingAgents: Multi-Agents LLM Financial Trading Framework.* arXiv:2412.20138.
- Shi, Y. et al. *Kronos: A Foundation Model for the Language of Financial Markets.* arXiv:2508.02739 (AAAI 2026).
- Tauric Research. *Trading-R1* technical report. arXiv:2509.11420.
- Freqtrade contributors. *Freqtrade: A Cryptocurrency Trading Bot.* JOSS, DOI: 10.21105/joss.04864.
- Kakushadze, Z. (2015). *101 Formulaic Alphas.* arXiv:1601.00991 (referenced by Vibe-Trading's factor zoo).

### 17.3 Models & tools
- Kronos weights on Hugging Face: `NeoQuasar/Kronos-mini`, `NeoQuasar/Kronos-small`, `NeoQuasar/Kronos-base`, tokenizers `NeoQuasar/Kronos-Tokenizer-2k` and `NeoQuasar/Kronos-Tokenizer-base`.
- LangGraph (LangChain), LiteLLM, Ollama, vLLM, FastAPI, Next.js, TimescaleDB, pgvector, python-telegram-bot.

### 17.4 Data sources (to integrate, subject to their terms)
- Yahoo Finance (via yfinance / idx), MSN Money (via idx), idx.co.id, KSEI, Indo Premier (IPOT), Kontan RSS, CNBC Indonesia RSS (via idx).
- FRED (St. Louis Fed), SEC EDGAR, Bank Indonesia (BI-Rate, JISDOR), BPS, ECB reference rates (Frankfurter), GDELT Project.
- Reddit API, StockTwits, Polymarket, ccxt (public crypto exchange data).
- Optional paid: Twelve Data, Polygon/Massive, Finnhub, Marketaux, X API, TradingEconomics.

---

## 18. Disclaimer

ARAH is a personal research tool. Its outputs are **informational and educational, not financial, investment or trading advice**. All forecasts are probabilistic and can be wrong. Past performance, including the system's own track record, does not guarantee future results. The owner is solely responsible for any investment decision.

---

## 19. Implementation status (app v0.1, 2026-11-12)

### Built and tested
| Area | Status |
|---|---|
| Daily brief: world direction, headline assets, reasons | Done. Rule-based always; AI team when an OpenRouter key with credit is present. |
| Forecasts for 1h, 4h, 1d, 1w, 2w, 3w, 1m and custom horizons | Done: filtered historical simulation, level-touch probabilities, fan chart. |
| FX watch level (Aman / Waspada / Siaga / Bahaya) and level alerts | Done. |
| Stock picks for Indonesia (30 stocks) and US (25 stocks) with 3 strengths, why enter, risks, plan | Done. Lists stay empty when nothing passes. |
| AI analyst team: desks for ID, US, JP, SG and global, bull, bear, chief strategist | Done, with citation checks and a 6-point cap on probability nudges. Runs on DeepSeek through OpenRouter by default, with the Claude Code CLI on the owner's Claude plan as the automatic fallback (the order can be reversed with `ARAH_LLM_PROVIDER=claude`). Both were verified live end to end: a full brief on DeepSeek took 8 calls, about 112 seconds and about US$0.03; the Claude fallback took over when OpenRouter had no credit. |
| Forecast ledger, scoring, track record page, walk-forward validation | Done. 133 asset and horizon pairs tested. |
| Web dashboard (Astryx), bilingual, light and dark | Done. 26 browser checks pass on a phone-sized screen. |
| Telegram bot and scheduled briefs | Written and unit-tested in parts; not run against Telegram itself (no token in the build environment). |
| CLI, installer, systemd unit, single-user login | Done. |

### Summary page (added after first use)
The home page was rebuilt around four questions for a newcomer: Indonesia, abroad (US, Japan, Singapore, China),
rupiah against the dollar, rupiah against the yuan. Each shows "now" and "next month" as good, neutral/unclear or
not good, with one reason; "Why?" and "See the chart" are the only two further steps. A China desk, the Shanghai
index and a computed CNY/IDR rate were added for it. The Telegram brief uses the same format.

### Added after first use (all run live once)
BCA e-Rate as the rate on screen (bca.co.id), this week's event calendar, foreign flow read from headlines by the
Indonesia desk, Telegram alerts when an answer changes, an exchange calculator, a 7-day report card, a free-question
box ("Ask ARAH"), and `setup.sh`, a one-command VPS setup with a systemd service. The systemd step and Telegram
delivery could not be run in the build environment.

### Changes from the PRD, with reasons
| PRD | Built | Why |
|---|---|---|
| Kronos as the core forecaster | Statistical simulation | It runs on a small VPS with no GPU or model download and could be validated on real data here. Kronos stays the next upgrade and must beat this baseline in the same test before it replaces it. |
| Postgres, Redis, Next.js, Docker | SQLite, in-process scheduler, Vite + React, plain venv | One user on a small VPS. Fewer moving parts to install and keep alive. |
| `idx` binary for IDX data | Yahoo Finance | One data path for every market in v0.1. `idx` adds foreign flow and bandarmology and is the next data upgrade. |
| USD/IDR alert levels 17,500 / 18,000 / 18,500 | 18,000 / 18,500 / 19,000 | USD/IDR was already at 18,228 when the app was built. Editable in Settings. |

### Findings from testing
- The 90% range held the outcome 83% to 99% of the time (median 90%). Ranges are trustworthy; for rupiah crosses they are slightly too wide.
- Price-only direction is near a coin flip. Only 3 of 133 pairs passed the strict direction test, which is about what chance alone would give. The app therefore says "unclear" often, on purpose.
- Yahoo served four wrong daily USD/IDR closes in a row (about 3.5% off). Before a filter for this was added, the app showed a 53% chance of touching 18,500 within a week and a "Siaga" level; after it, 12% and "Aman".

### Not built yet
Kronos, `idx` integration (foreign flow, broker summary, bandarmology), paper trading, forum and social sentiment, coal and nickel prices, Japan and Singapore stock lists, weekly agent self-review, TOTP login, backups command.
