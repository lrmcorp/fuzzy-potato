# ARAH design direction

The direction comes from the owner's redesign pack ("ARAH Redesign", SPEC.md with mockups for desktop 1280px and
phone 390px). This file records what was built from it and the choices the owner made on top. Design tokens live in
`web/src/tokens.css`, copied unchanged from the pack.

Reading this as: a personal Indonesian stock and FX research app for one newcomer, mostly on a phone, in a calm and
data-first style with charts and numbers instead of paragraphs, dial ENERGY 1 / RHYTHM 2 / MOTION 1.

## Owner decisions

| Decision | Source |
|---|---|
| Numbers in Indonesian style: 5.311,36 · Rp 18.200 · −1,6% (U+2212 minus); ranges as "a sampai b" | Owner chose the pack's format over the earlier 1,000 style |
| Stock actions Masuk / Masuk bertahap / Tunggu / Hindari, thresholds in `arah/verdict_rules.py` | Owner approved the pack's thresholds: Masuk = score ≥ 70 and chance ≥ 60%; bertahap = score ≥ 70, chance < 60%; Tunggu = 40 to 69 or no data; Hindari = score < 40 or chance ≤ 40% |
| Markets, indices and FX show a direction (Naik / Datar / Turun) and the gauge from Menekan to Mendukung | Pack SPEC; the old words Layak, Bagus, Netral and Kurang bagus are gone from the app, the bot and notifications |
| Each phase is built, tested and merged without waiting | Owner's choice for this redesign |

## Decisions and their reasons

| Decision | Reason |
|---|---|
| Light mode only, Inter with tabular figures | Pack non-negotiable; tabular figures keep prices aligned in columns. |
| Desktop: top bar with Ringkasan · Pasar · Berita · Peringatan (badge "N aktif") · Atur, a search field focused by `/`, and the data-freshness chip | Every page is one click away, and search is the fastest way to any stock. |
| Phone: bottom tab bar Ringkasan · Pasar · Cari · Peringatan · Atur (56px plus safe area); asset pages swap it for an action bar [☆] [Pasang peringatan] [Tanya] | Thumb reach; on an asset page the next action matters more than navigation. |
| One verdict vocabulary everywhere, each with its own mark (● ◐ ■ ▼) | Meaning never rests on colour alone, and web, push and Telegram never disagree. |
| Colour follows what a move means for a rupiah holder; the ▲/▼ arrow follows the price | A rising USD/IDR is drawn ▲ in orange: up in price, bad for the owner. |
| The asset page opens with the Keputusan card, then 6 months of history with a +1/2/3 month forecast (50% and 90% bands, labelled at the right edge, with a table view) | The answer first, then the evidence; the bands carry the range, so there is no separate "kisaran" block. |
| The technique list shows only the techniques used plus the best comparison; the rest sit behind one button | A newcomer sees what decided the answer, not every method that was tried. |
| Picks show a trade-plan ruler (batas rugi, area beli, kini, target 1 and 2) and "Hitung lot" replaces the currency calculator | Risk and reward on one line; position size is the question a plan raises next. |
| One alert sheet everywhere: the direction comes from the current price, presets come from the trade plan (else the 9-in-10 range), and "Batalkan" removes the whole group | Setting an alert takes 2 to 3 taps from search, the watchlist, the asset page or a pick. |
| Data freshness is one component: the time when live, an amber "Tertunda 15 mnt" chip when Stockbit is not connected, "Sinyal dijeda" when data is over a day old | The owner can reconnect Stockbit from the chip by pasting a fresh session; delayed data is never shown next to a green "live" dot. |
| Charts are drawn at the width they are shown | The 12px labels stay 12px on a 390px phone instead of shrinking with the drawing. |

## Honesty rules for the interface

- Every forecast sentence names an actor ("ARAH memperkirakan…"); odds are written as "1 dari 2" and "9 dari 10".
- The stock verdict comes from a fixed rule not yet tested on past data.
- Community posts from Stockbit are labelled as unverified opinion.
- Empty, loading and error states say what is missing; no "—" in empty cells.
- The footer reads "ARAH (AI Research & Analysis Hub) by LRM Corporation - Internal Use Only" (the owner's wording, replacing the pack's disclaimer).
