# ARAH design direction

Reading this as: a personal market briefing for one Indonesian investor who wants the answer first,
in a calm morning-newspaper style, dial ENERGY 1 / RHYTHM 2 / MOTION 1.

## Who reads it and what they need

One person, new to markets, usually on a phone. The first screen answers four questions and nothing else:
is Indonesia good or not, is abroad good or not, how is the rupiah against the dollar, and against the yuan.
Each has two answers (now, next month) and one reason. Every stock carries one word to act on (Layak, Tunggu,
Hindari) with its score and three reasons. Everything else is at most two taps away.

## Decisions and their reasons

| Decision | Reason |
|---|---|
| One reading column, about 46rem wide | The brief is read top to bottom like an article, not scanned like a dashboard. |
| The conclusion sentence is set in a serif, everything else in the theme sans | The serif marks "this is the verdict" the way a newspaper lede does. It is the typographic voice of the product. |
| The horizon strip (1 hour to 1 month) repeats on every asset | It is the identity motif: the same seven steps, the same glyphs, everywhere. |
| Direction uses glyphs in ink colour: ▲ ▼ ◆ | Green and red would be wrong: a rising USD/IDR is bad news for a rupiah holder, a rising IHSG is good. Shape carries direction, text carries meaning. |
| One accent, deep teal, on the selected horizon and the primary button only | Teal stays clear of the red, amber and green reserved for the watch level, so the accent never reads as a market signal. |
| Green, grey and red appear on answer tags (Bagus, Netral, Kurang bagus), verdict tags (Layak, Tunggu, Hindari) and the watch level | Colour means "good or not for you", never "price up or down": a rising USD/IDR is tagged red because the rupiah is weaker. Every tag carries its word, so colour is never the only signal. Netral and Tunggu are grey: no side is ahead. |
| Five destinations in a bottom bar on phones (Ringkasan, Pasar, Berita, Peringatan, Atur), a left rail from 60rem | The owner reads on a phone; the bottom bar sits within thumb reach. The owner chose this layout. |
| The bottom bar has words, no icons | Five short words read faster for a newcomer than five generic glyphs, and none of the stock icon shapes means "rupiah" or "alert level" better than the word. |
| Sub-sections are a row of chips that scrolls sideways on a phone | Seven segments (Pilihan to Hitung) fit one thumb swipe instead of wrapping into a wall of buttons. Each chip is a real button with a pressed state. |
| Market lists are rows, not tables: name, a 3-month line, price and today's change, the verdict under the price | Rows survive a 360px screen without sideways scrolling; the line shows the trend at a glance. Stocks are sorted by verdict score, best first. |
| The stock page opens with the price and chart (today, 1M, 3M, 1Y, 5Y), then the verdict card, then four tabs: Analisa, Bandar & asing, Berita, Detail | The owner pointed at the terminal's stock page as the reference for what goes where; the order is price, then the answer, then the evidence. The look stays ARAH's own. |
| The verdict word (Layak, Tunggu, Hindari) is set in the serif, with the score and a meter marked at 45 and 65 | The serif is the product's voice for conclusions; the marks show how far the score is from the next word. |
| News is a numbered list ranked by importance, with "N media" next to the source | The order is the ranking, so numbers carry meaning; how many outlets ran a story is the plainest proof that it matters. |
| Notifications go to the phone through the browser (web push), set up on the Peringatan page | The owner chose phone notifications without another account. iPhones need the app on the Home Screen first, and the page says so. |
| Rules and whitespace separate sections; cards only for stock picks | A stock pick is a discrete item that can be compared and reordered. Sections of a brief are not. |
| Light mode only | The owner asked for one bright look everywhere; no dark mode or theme switch. |
| The summary is four cards with a chart each: price, now and next month, a 3-month line with the next-month cone, and the range | The owner found the text-heavy brief confusing. Reasons, sources and test results moved behind "Kenapa?" and "Data lain" on the detail page. |
| The asset page opens with today's live chart, then the forecast: conclusion, projection chart, and each technique's view | The owner wants the chart and the system's analysis first. Short-horizon detail, reasons and sources sit behind two collapsed sections. |
| A 1, 2 or 3-month filter sits directly above what it changes (summary cards, forecast) | One control per question, placed where its effect is seen. |
| Live candles are ink only: hollow for a rising minute, filled for a falling one | Green and red already mean good or bad for the owner; candles must not reuse them for up and down. |
| Technique paths use the first three slots of the validated categorical palette, each with its own dash pattern and an end label | Three lines pass the colour-blind checks together; dashes and labels mean colour is never the only cue. |
| Motion: hover and focus states only | Numbers that move on their own distract from reading them. Respects reduced motion by having none to reduce. |
| Today's chart and long ranges are drawn as a line; 1M keeps ink candles | A minute-by-minute candle row is noise on a phone; a line reads like the terminal the owner uses. One month of daily candles still shows each day's range. |
| Astryx neutral theme as the base | Quiet defaults, accessible controls, and tokens that the few custom pieces reuse. |

## Honesty rules for the interface

- A percentage is always labelled as a chance, never as a promise.
- Every forecast shows whether it passed the historical test, in words.
- When data is stale or thin, the screen says so next to the number it affects.
- Empty lists stay empty and say why. No filler picks.
- The stock verdict says it comes from a fixed rule not yet tested on past data, on the card itself.
- Community posts from Stockbit are labelled as unverified opinion wherever they appear.
