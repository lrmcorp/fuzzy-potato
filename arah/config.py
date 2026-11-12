from __future__ import annotations

import os
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
    budget_usd_month: float = field(default_factory=lambda: _float("ARAH_BUDGET_USD_MONTH", 30.0))
    budget_usd_day: float = field(default_factory=lambda: _float("ARAH_BUDGET_USD_DAY", 2.0))

    telegram_token: str = field(default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", ""))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "arah.db"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openrouter_key)

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
