from __future__ import annotations

import asyncio
import html
import logging
import re
import secrets
from pathlib import Path

import typer

from .config import get_settings

app = typer.Typer(add_completion=False, help="ARAH: daily market direction briefings.", no_args_is_help=True)


def _plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text))


def _rt():
    from .db import DB
    from .runtime import Runtime

    s = get_settings()
    return Runtime(DB(s.db_path), s)


@app.command()
def init(force: bool = typer.Option(False, help="Overwrite an existing .env")):
    """Create a .env file with a generated password and secret."""
    path = Path(".env")
    if path.exists() and not force:
        typer.echo(".env already exists. Use --force to overwrite it.")
        raise typer.Exit(1)
    password = secrets.token_urlsafe(12)
    path.write_text(
        "# ARAH configuration. Keep this file private.\n"
        f"ARAH_PASSWORD={password}\n"
        f"ARAH_SECRET={secrets.token_hex(32)}\n"
        "ARAH_HOST=127.0.0.1\nARAH_PORT=8787\nARAH_TIMEZONE=Asia/Jakarta\n\n"
        "# AI analyst team (optional). Get a key at openrouter.ai\n"
        "OPENROUTER_API_KEY=\n"
        "ARAH_MODEL_QUICK=deepseek/deepseek-v4.1-flash\nARAH_MODEL_DEEP=deepseek/deepseek-v4-pro\n"
        "ARAH_BUDGET_USD_MONTH=30\nARAH_BUDGET_USD_DAY=2\n\n"
        "# Telegram (optional). Token from @BotFather, chat id from @userinfobot\n"
        "TELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n"
    )
    path.chmod(0o600)
    typer.echo(f"Wrote .env. Dashboard password: {password}")
    typer.echo("Add OPENROUTER_API_KEY and the Telegram values to .env, then run: arah up")


@app.command()
def up(host: str = typer.Option(None), port: int = typer.Option(None)):
    """Run the dashboard, the scheduler and the Telegram bot."""
    import uvicorn

    s = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    host, port = host or s.host, port or s.port
    if host not in ("127.0.0.1", "localhost") and not s.password:
        typer.echo("Refusing to listen on a public address without ARAH_PASSWORD. Run `arah init` first.")
        raise typer.Exit(1)
    typer.echo(f"ARAH is starting on http://{host}:{port}")
    uvicorn.run("arah.api:create_app", factory=True, host=host, port=port, log_level="info")


@app.command()
def brief(lang: str = typer.Option(None, help="id or en")):
    """Build a fresh brief and print it."""
    from .telegram import format_brief

    rt = _rt()
    b = asyncio.run(rt.run_brief("cli", push=False))
    typer.echo(_plain(format_brief(b, lang or rt.db.get("lang", "id"))))


@app.command()
def forecast(asset: str, horizon: str = typer.Argument("1w"), lang: str = typer.Option(None)):
    """Forecast one asset, e.g. `arah forecast USDIDR 2w` or `arah forecast BBCA 4h`."""
    from .agents import get_insight
    from .data.yahoo import refresh_many
    from .service import build_view
    from .telegram import format_view
    from .universe import GAUGES, MACRO, resolve

    rt = _rt()
    a = resolve(asset)
    if not a:
        typer.echo(f"Unknown asset: {asset}")
        raise typer.Exit(1)
    asyncio.run(refresh_many(rt.db, [x.symbol for x in MACRO + GAUGES] + [a.symbol]))
    view = build_view(rt.db, a, horizon, insight=get_insight(rt.db, a.key), with_chart=False)
    typer.echo(_plain(format_view(view, lang or rt.db.get("lang", "id"))))


@app.command()
def recs(market: str = typer.Argument("id"), lang: str = typer.Option(None)):
    """Recommended stocks for `id` or `us`."""
    from .recommend import build_recs
    from .telegram import format_recs

    rt = _rt()
    asyncio.run(rt.refresh_data(stocks=True))
    out = asyncio.run(build_recs(rt.db))
    typer.echo(_plain(format_recs(out, market.upper(), lang or rt.db.get("lang", "id"))))


@app.command()
def validate():
    """Run the walk-forward test of the forecast model on all macro assets."""
    rt = _rt()
    asyncio.run(rt.refresh_data(stocks=False))
    asyncio.run(rt.validate_all())
    typer.echo("Validation finished. See the Track Record page.")


@app.command()
def doctor():
    """Check configuration and connectivity."""
    import httpx

    s = get_settings()
    typer.echo(f"data dir        : {s.data_dir.resolve()}")
    typer.echo(f"dashboard login : {'on' if s.password else 'OFF (set ARAH_PASSWORD)'}")
    typer.echo(f"OpenRouter key  : {'set' if s.llm_enabled else 'not set (rule-based mode)'}")
    typer.echo(f"Telegram        : {'set' if s.telegram_enabled else 'not set'}")
    for name, url in (("Yahoo Finance", "https://query1.finance.yahoo.com/v8/finance/chart/IDR=X?range=1d&interval=1h"),
                      ("Google News", "https://news.google.com/rss/search?q=rupiah&hl=id&gl=ID&ceid=ID:id"),
                      ("OpenRouter", "https://openrouter.ai/api/v1/models")):
        try:
            code = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).status_code
        except httpx.HTTPError as e:
            code = f"failed ({e.__class__.__name__})"
        typer.echo(f"{name:<16}: {code}")


if __name__ == "__main__":
    app()
