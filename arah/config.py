from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.environ.get("ARAH_ENV_FILE", ".env"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("ARAH_DATA_DIR", "data")))
    host: str = field(default_factory=lambda: os.environ.get("ARAH_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _int("ARAH_PORT", 8787))
    password: str = field(default_factory=lambda: os.environ.get("ARAH_PASSWORD", ""))
    secret: str = field(default_factory=lambda: os.environ.get("ARAH_SECRET", ""))
    timezone: str = field(default_factory=lambda: os.environ.get("ARAH_TIMEZONE", "Asia/Jakarta"))

    openrouter_key: str = field(default_factory=lambda: os.environ.get("OPENROUTER_API_KEY", ""))
    openrouter_url: str = field(
        default_factory=lambda: os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )
    model_quick: str = field(
        default_factory=lambda: os.environ.get("ARAH_MODEL_QUICK", "deepseek/deepseek-v4.1-flash")
    )
    model_deep: str = field(
        default_factory=lambda: os.environ.get("ARAH_MODEL_DEEP", "deepseek/deepseek-v4-pro")
    )
    # Main service for the analyst team: "openrouter" (DeepSeek) or "claude" (the Claude Code CLI
    # signed in with your own Claude plan). The other one is the fallback when it is set up.
    llm_fallback: bool = field(default_factory=lambda: os.environ.get("ARAH_LLM_FALLBACK", "on").lower() != "off")
    llm_provider: str = field(default_factory=lambda: os.environ.get("ARAH_LLM_PROVIDER", "openrouter").lower())
    claude_bin: str = field(default_factory=lambda: os.environ.get("ARAH_CLAUDE_BIN", "claude"))
    claude_quick: str = field(default_factory=lambda: os.environ.get("ARAH_CLAUDE_MODEL_QUICK", "haiku"))
    claude_deep: str = field(default_factory=lambda: os.environ.get("ARAH_CLAUDE_MODEL_DEEP", "sonnet"))
    claude_calls_day: int = field(default_factory=lambda: _int("ARAH_CLAUDE_CALLS_DAY", 150))
    budget_usd_month: float = field(default_factory=lambda: _float("ARAH_BUDGET_USD_MONTH", 30.0))
    budget_usd_day: float = field(default_factory=lambda: _float("ARAH_BUDGET_USD_DAY", 2.0))

    telegram_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", ""))
    # The address the owner opens ARAH at, for links in Telegram messages. Empty means no links.
    public_url: str = field(default_factory=lambda: os.environ.get("ARAH_PUBLIC_URL", "").rstrip("/"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "arah.db"

    @property
    def claude_available(self) -> bool:
        return shutil.which(self.claude_bin) is not None

    @property
    def provider_order(self) -> list[str]:
        """Providers to try, first to last. The first is the main one, the rest are fallbacks."""
        have = {"openrouter": bool(self.openrouter_key), "claude": self.claude_available}
        first = "claude" if self.llm_provider == "claude" else "openrouter"
        second = "openrouter" if first == "claude" else "claude"
        order = [first] + ([second] if self.llm_fallback else [])
        return [p for p in order if have[p]]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.provider_order)

    @property
    def llm_names(self) -> dict:
        models = {"openrouter": (self.model_quick, self.model_deep), "claude": (self.claude_quick, self.claude_deep)}
        order = self.provider_order
        if not order:
            return {"provider": "none", "quick": "", "deep": "", "fallback": None}
        return {"provider": order[0], "quick": models[order[0]][0], "deep": models[order[0]][1],
                "fallback": order[1] if len(order) > 1 else None}

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)


def get_settings() -> Settings:
    return Settings()


# Horizon presets. Short horizons run on hourly bars, the rest on daily bars.
HORIZONS: dict[str, tuple[str, int]] = {
    "1h": ("1h", 1),
    "4h": ("1h", 4),
    "1d": ("1d", 1),
    "1w": ("1d", 5),
    "2w": ("1d", 10),
    "3w": ("1d", 15),
    "1m": ("1d", 21),
}
DEFAULT_HORIZONS = list(HORIZONS)

# WIB times of the scheduled briefs.
BRIEF_SCHEDULE = [
    ("pre_idx", "07:30"),
    ("midday", "12:00"),
    ("post_idx", "16:30"),
    ("pre_us", "20:00"),
    ("us_recap", "05:00"),
]
WEEKLY_OUTLOOK = ("sun", "19:00")


def parse_horizon(text: str, days_per_week: int = 5) -> tuple[str, int, str]:
    """Turn '1h', '6h', '3d', '2w', '1m' into (interval, steps, canonical label)."""
    t = text.strip().lower()
    if t in HORIZONS:
        interval, steps = HORIZONS[t]
        if interval == "1d" and days_per_week == 7:
            steps = {"1d": 1, "1w": 7, "2w": 14, "3w": 21, "1m": 30}[t]
        return interval, steps, t
    if len(t) < 2 or not t[:-1].isdigit():
        raise ValueError(f"unknown horizon: {text}")
    n, unit = int(t[:-1]), t[-1]
    if n <= 0:
        raise ValueError(f"unknown horizon: {text}")
    if unit == "h":
        if n > 48:
            raise ValueError("hourly horizons go up to 48h; use days instead")
        return "1h", n, t
    per_week = days_per_week
    if unit == "d":
        steps = n
    elif unit == "w":
        steps = n * per_week
    elif unit == "m":
        steps = n * (30 if per_week == 7 else 21)
    else:
        raise ValueError(f"unknown horizon: {text}")
    if steps > 130:
        raise ValueError("horizon too long; the maximum is about 6 months")
    return "1d", steps, t
