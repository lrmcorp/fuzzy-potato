"""The one place where ARAH's words for a decision are set. Web, push notifications and Telegram all
read from here, so a stock is never "Masuk" in one place and something else in another.

Stocks get an action (approved by the owner, redesign pack prompt 03):

  Masuk           technical score >= 70 and chance of a rise in 1 month >= 60%
  Masuk bertahap  technical score >= 70 and chance below 60%
  Tunggu          technical score 40 to 69, or not enough data
  Hindari         technical score below 40, or chance of a rise <= 40%

Markets, indices and currencies get a direction for the forecast: Naik, Datar or Turun.
"""
from __future__ import annotations

MASUK_SCORE = 70
MASUK_CHANCE = 0.60
HINDARI_SCORE = 40
HINDARI_CHANCE = 0.40

# key -> (label, icon name used by the web app, tone)
ACTIONS = {
    "masuk": ("Masuk", "full", "green"),
    "bertahap": ("Masuk bertahap", "half", "green"),
    "tunggu": ("Tunggu", "square", "grey"),
    "hindari": ("Hindari", "down", "orange"),
}
DIRECTIONS = {"naik": ("Naik", "up", "green"), "datar": ("Datar", "square", "grey"), "turun": ("Turun", "down", "orange"),
              "belum_jelas": ("Belum jelas arahnya", "square", "grey")}
# "Datar" is only honest when the range is narrow too: a flat middle with a range wider than this either way
# means ARAH does not know, and says so.
WIDE_RANGE = 0.05
# Telegram and notifications have no icons of their own; these characters stand in for them.
TEXT_ICON = {"full": "●", "half": "◐", "square": "■", "down": "▼", "up": "▲"}


def action(score: float | None, p_up: float | None) -> str:
    if score is None or p_up is None:
        return "tunggu"
    if score < HINDARI_SCORE or round(p_up, 2) <= HINDARI_CHANCE:
        return "hindari"
    if score >= MASUK_SCORE:
        return "masuk" if round(p_up, 2) >= MASUK_CHANCE else "bertahap"
    return "tunggu"


def direction(p_up: float | None) -> str:
    """Forecast direction of the price itself, not whether it is good for the owner."""
    if p_up is None:
        return "datar"
    p = round(p_up, 2)
    return "naik" if p >= MASUK_CHANCE else "turun" if p <= HINDARI_CHANCE else "datar"


def direction_range(p_up: float | None, lo: float | None, hi: float | None, s0: float | None) -> str:
    """Direction, with "belum_jelas" instead of "datar" when the 9-in-10 range spans more than 5% either way."""
    d = direction(p_up)
    if d == "datar" and lo and hi and s0 and (hi / s0 - 1 > WIDE_RANGE or 1 - lo / s0 > WIDE_RANGE):
        return "belum_jelas"
    return d


def sentence(key: str, score: float | None, p_up: float | None) -> str:
    """At most eight words: why this action."""
    if key == "masuk":
        return "Tren kuat dan peluang naik mendukung."
    if key == "bertahap":
        return "Tren kuat, arah sebulan belum jelas."
    if key == "hindari":
        return "Peluang turun sebulan ini lebih besar." if p_up is not None and round(p_up, 2) <= HINDARI_CHANCE \
            else "Kondisi teknikal lemah, risiko masih besar."
    if score is None or p_up is None:
        return "Data belum cukup untuk memutuskan."
    return "Sinyal campur, tunggu arah lebih jelas."


def tag(key: str) -> dict:
    """What the web app needs to draw the tag."""
    table = ACTIONS if key in ACTIONS else DIRECTIONS
    label, icon, tone = table[key]
    return {"key": key, "label": label, "icon": icon, "tone": tone}


def text_tag(key: str) -> str:
    t = tag(key)
    return f"{TEXT_ICON[t['icon']]} {t['label']}"
