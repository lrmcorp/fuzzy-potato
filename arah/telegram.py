"""Telegram bot over plain HTTPS long polling. Only the configured chat is answered."""
from __future__ import annotations

import asyncio
import html
import logging
import time

import httpx

from .agents import analyze_asset, get_insight
from .config import Settings, parse_horizon
from .db import DB
from .service import all_horizons, build_view
from .signals import fmt_num
from .universe import resolve

log = logging.getLogger("arah.telegram")
ARROW = {"up": "▲", "down": "▼", "flat": "◆"}
DIR_WORD = {"id": {"up": "cenderung naik", "down": "cenderung turun", "flat": "belum jelas"},
            "en": {"up": "leans up", "down": "leans down", "flat": "unclear"}}

HELP = {
    "id": ("<b>ARAH</b>\n/brief : ringkasan arah dunia sekarang\n/arah USD 1w : prakiraan satu aset (contoh: /arah BBCA 2w, /arah IHSG 4h)\n"
           "/analisa BBCA : analisa mendalam oleh tim AI\n/rek id atau /rek us : saham rekomendasi\n"
           "/alert USDIDR &gt; 18500 : pasang peringatan harga\n/alerts : daftar peringatan\n/lang id atau /lang en\n\n"
           "Rentang waktu: 1h 4h 1d 1w 2w 3w 1m, atau bebas seperti 3d, 6h, 5w."),
    "en": ("<b>ARAH</b>\n/brief : where the world is heading now\n/arah USD 1w : forecast for one asset (e.g. /arah BBCA 2w, /arah IHSG 4h)\n"
           "/analisa BBCA : deep analysis by the AI team\n/rek id or /rek us : recommended stocks\n"
           "/alert USDIDR &gt; 18500 : set a price alert\n/alerts : list alerts\n/lang id or /lang en\n\n"
           "Horizons: 1h 4h 1d 1w 2w 3w 1m, or free-form such as 3d, 6h, 5w."),
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def format_view(view: dict, lang: str) -> str:
    if view.get("error"):
        return {"id": "Data untuk aset ini belum tersedia.", "en": "No data for this asset yet."}[lang]
    f, d = view["forecast"], view["decimals"]
    lines = [f"{ARROW[view['direction']]} <b>{esc(view['name_en'] if lang == 'en' else view['name'])}</b>  {fmt_num(f['s0'], d, lang)}",
             esc(view["summary"][lang]), ""]
    lines.append("<b>Kenapa</b>" if lang == "id" else "<b>Why</b>")
    for r in view["reasons"][:5]:
        mark = "▲" if r["lean"] > 0 else "▼" if r["lean"] < 0 else "•"
        lines.append(f"{mark} {esc(r['text'][lang])}")
    if view.get("watch"):
        lines.append(("\n<b>Yang perlu diawasi:</b> " if lang == "id" else "\n<b>What to watch:</b> ") + esc(view["watch"][lang]))
    vg = view.get("vigilance")
    if vg:
        lines.append("")
        lines.append(f"<b>{'Tingkat kewaspadaan' if lang == 'id' else 'Watch level'}: {esc(vg['name'][lang])}</b>")
    for level, p in sorted(f.get("touch", {}).items(), key=lambda x: float(x[0])):
        word = "menyentuh" if lang == "id" else "touching"
        lines.append(f"{'Peluang' if lang == 'id' else 'Chance of'} {word} {fmt_num(float(level), d, lang)}: {p * 100:.0f}%")
    val = view.get("validation")
    if val and val.get("grade"):
        note = {"validated": ("Arah dan rentang lolos uji historis.", "Direction and range passed the historical test."),
                "range_only": ("Rentang lolos uji historis; arah belum terbukti lebih baik dari tebakan.",
                               "Range passed the historical test; direction is not proven better than a guess."),
                "experimental": ("Masih eksperimental untuk aset dan rentang waktu ini.", "Still experimental for this asset and horizon."),
                "insufficient": ("Riwayat data belum cukup untuk diuji.", "Not enough history to test.")}[val["grade"]]
        lines.append(f"\n<i>{note[0 if lang == 'id' else 1]}</i>")
    for n in view.get("notes", []):
        lines.append(f"<i>{esc(n[lang])}</i>")
    return "\n".join(lines)


def format_brief(brief: dict, lang: str) -> str:
    lines = [f"<b>{esc(brief['headline'][lang])}</b>", "",
             f"<b>{'Arah dunia' if lang == 'id' else 'World direction'}: {esc(brief['world']['name'][lang])}</b>",
             esc(brief["world"]["summary"][lang])]
    lines += [f"• {esc(p['text'][lang])}" for p in brief["world"]["points"]]
    for v in brief["assets"]:
        d = v["decimals"]
        lines.append("")
        lines.append(f"{ARROW[v['direction']]} <b>{esc(v['name_en'] if lang == 'en' else v['name'])}</b> {fmt_num(v['forecast']['s0'], d, lang)}")
        strip = "  ".join(f"{h['horizon']} {ARROW[h['direction']]}{h['p_up'] * 100:.0f}%" for h in v.get("horizons", []))
        lines.append(f"<code>{strip}</code>")
        if v["reasons"]:
            lines.append(f"• {esc(v['reasons'][0]['text'][lang])}")
        if v.get("vigilance"):
            vg = v["vigilance"]
            lines.append(f"{'Kewaspadaan' if lang == 'id' else 'Watch level'}: <b>{esc(vg['name'][lang])}</b> "
                         f"({'peluang sentuh' if lang == 'id' else 'chance of touching'} {fmt_num(vg['level'], d, lang)}: {vg['p'] * 100:.0f}%)")
    foot = ("Angka % adalah peluang naik menurut model. Ini bukan saran investasi." if lang == "id"
            else "Percentages are the model's chance of a rise. This is not investment advice.")
    lines += ["", f"<i>{foot}</i>"]
    return "\n".join(lines)


def format_recs(recs: dict, market: str, lang: str) -> str:
    cards = recs.get(market, [])
    if not cards:
        n = (recs.get("screened") or {}).get(market, 0)
        return (f"Tidak ada saham yang lolos saringan hari ini (dari {n} yang diperiksa). Lebih baik menunggu daripada memaksa."
                if lang == "id" else f"No stock passed the screen today (out of {n} checked). Waiting beats forcing a pick.")
    out = []
    for c in cards:
        d = c["decimals"]
        plan = c["plan"]
        out.append(f"<b>{esc(c['key'])}</b> {esc(c['name'])}  {fmt_num(c['price'], d, lang)}")
        out += [f"{i}. {esc(s[lang])}" for i, s in enumerate(c["strengths"], 1)]
        out.append(("<b>Kenapa masih layak:</b> " if lang == "id" else "<b>Why still worth it:</b> ") + esc(c["why"][lang]))
        out.append(f"{'Masuk' if lang == 'id' else 'Entry'} {fmt_num(plan['entry'][0], d, lang)} - {fmt_num(plan['entry'][1], d, lang)} | "
                   f"Target {fmt_num(plan['targets'][0], d, lang)} | {'Batas rugi' if lang == 'id' else 'Stop'} {fmt_num(plan['stop'], d, lang)}")
        out.append(("Risiko: " if lang == "id" else "Risk: ") + esc(c["risks"][0][lang]))
        out.append("")
    return "\n".join(out)


class Bot:
    def __init__(self, db: DB, settings: Settings, on_brief=None):
        self.db, self.settings, self.on_brief = db, settings, on_brief
        self.base = f"https://api.telegram.org/bot{settings.telegram_token}"
        self.offset = 0

    @property
    def lang(self) -> str:
        return self.db.get("lang", "id")

    async def send(self, text: str) -> bool:
        if not self.settings.telegram_enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                for chunk in _chunks(text, 3900):
                    r = await client.post(f"{self.base}/sendMessage", json={
                        "chat_id": self.settings.telegram_chat_id, "text": chunk, "parse_mode": "HTML",
                        "disable_web_page_preview": True})
                    if r.status_code != 200:
                        log.warning("telegram send failed: %s %s", r.status_code, r.text[:200])
                        return False
            return True
        except httpx.HTTPError as e:
            log.warning("telegram send failed: %s", e)
            return False

    async def handle(self, text: str) -> str:
        lang = self.lang
        parts = text.strip().split()
        if not parts:
            return HELP[lang]
        cmd = parts[0].lower().split("@")[0]
        args = parts[1:]
        if cmd in ("/start", "/help"):
            return HELP[lang]
        if cmd == "/lang" and args and args[0].lower() in ("id", "en"):
            self.db.set("lang", args[0].lower())
            return "Bahasa: Indonesia" if args[0].lower() == "id" else "Language: English"
        if cmd == "/brief":
            brief = self.db.latest_report("brief", max_age=3 * 3600)
            if not brief and self.on_brief:
                brief = await self.on_brief()
            return format_brief(brief, lang) if brief else ("Brief belum tersedia." if lang == "id" else "No brief yet.")
        if cmd in ("/rek", "/rec"):
            market = (args[0].upper() if args else "ID")
            recs = self.db.latest_report("recs")
            if not recs or market not in ("ID", "US"):
                return "Gunakan /rek id atau /rek us." if lang == "id" else "Use /rek id or /rek us."
            return format_recs(recs, market, lang)
        if cmd == "/alerts":
            rows = self.db.q("SELECT * FROM alerts WHERE triggered_at IS NULL ORDER BY id")
            if not rows:
                return "Belum ada peringatan aktif." if lang == "id" else "No active alerts."
            return "\n".join(f"#{r['id']} {r['asset']} {r['op']} {fmt_num(r['level'], 2, lang)}" for r in rows)
        if cmd == "/alert":
            return self._add_alert(args, lang)
        if cmd in ("/arah", "/fx", "/forecast", "/analisa", "/analyze") or not cmd.startswith("/"):
            words = args if cmd.startswith("/") else parts
            asset = next((a for w in words if (a := resolve(w))), None)
            if not asset:
                return ("Aset tidak dikenali. Contoh: /arah USD 1w, /arah BBCA 2w." if lang == "id"
                        else "Unknown asset. Examples: /arah USD 1w, /arah BBCA 2w.")
            horizon = "1w"
            for w in words:
                try:
                    horizon = parse_horizon(w, asset.days_per_week)[2]
                    break
                except ValueError:
                    continue
            if cmd in ("/analisa", "/analyze"):
                ins = await analyze_asset(self.db, self.settings, asset)
                if ins is None and not self.settings.llm_enabled:
                    note = ("Analisa AI belum aktif (kunci OpenRouter belum diisi). Ini hasil model statistik:\n\n" if lang == "id"
                            else "AI analysis is off (no OpenRouter key). Here is the statistical model's view:\n\n")
                    return note + format_view(build_view(self.db, asset, horizon, with_chart=False), lang)
            view = build_view(self.db, asset, horizon, insight=get_insight(self.db, asset.key), with_chart=False)
            text_out = format_view(view, lang)
            if not view.get("error"):
                rows = all_horizons(self.db, asset, get_insight(self.db, asset.key))
                strip = "  ".join(f"{h['horizon']} {ARROW[h['direction']]}{h['p_up'] * 100:.0f}%" for h in rows)
                text_out += f"\n\n<code>{strip}</code>"
            return text_out
        return HELP[lang]

    def _add_alert(self, args: list[str], lang: str) -> str:
        usage = "Contoh: /alert USDIDR > 18500" if lang == "id" else "Example: /alert USDIDR > 18500"
        if len(args) != 3 or args[1] not in (">", "<"):
            return usage
        asset = resolve(args[0])
        try:
            level = float(args[2].replace(".", "").replace(",", ".")) if lang == "id" and "," in args[2] else float(args[2].replace(",", ""))
        except ValueError:
            return usage
        if not asset or level <= 0:
            return usage
        self.db.x("INSERT INTO alerts (asset, op, level, created_at) VALUES (?,?,?,?)", (asset.key, args[1], level, int(time.time())))
        return (f"Peringatan dipasang: {asset.name} {args[1]} {fmt_num(level, asset.decimals, lang)}" if lang == "id"
                else f"Alert set: {asset.name} {args[1]} {fmt_num(level, asset.decimals, lang)}")

    async def poll_forever(self) -> None:
        if not self.settings.telegram_enabled:
            return
        log.info("telegram bot polling started")
        async with httpx.AsyncClient(timeout=40) as client:
            while True:
                try:
                    r = await client.get(f"{self.base}/getUpdates", params={"timeout": 25, "offset": self.offset})
                    for upd in r.json().get("result", []):
                        self.offset = upd["update_id"] + 1
                        msg = upd.get("message") or {}
                        if str(msg.get("chat", {}).get("id")) != str(self.settings.telegram_chat_id):
                            continue
                        if msg.get("text"):
                            try:
                                reply = await self.handle(msg["text"])
                            except Exception:
                                log.exception("command failed")
                                reply = "Terjadi kesalahan saat memproses perintah." if self.lang == "id" else "Something went wrong handling that command."
                            await self.send(reply)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.warning("telegram poll error: %s", e)
                    await asyncio.sleep(5)


def _chunks(text: str, size: int):
    while text:
        if len(text) <= size:
            yield text
            return
        cut = text.rfind("\n", 0, size)
        cut = cut if cut > 0 else size
        yield text[:cut]
        text = text[cut:].lstrip("\n")

