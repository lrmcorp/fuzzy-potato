# ARAH design direction

Reading this as: a personal market briefing for one Indonesian investor who wants the answer first,
in a calm morning-newspaper style, dial ENERGY 1 / RHYTHM 2 / MOTION 1.

## Who reads it and what they need

One person, new to markets, usually on a phone. The first screen answers four questions and nothing else:
is Indonesia good or not, is abroad good or not, how is the rupiah against the dollar, and against the yuan.
Each has two answers (now, next month) and one reason. Everything else is at most two taps away:
"Why?" opens the reasons, and "See the chart" opens the detail page.

## Decisions and their reasons

| Decision | Reason |
|---|---|
| One reading column, about 720px wide | The brief is read top to bottom like an article, not scanned like a dashboard. |
| The conclusion sentence is set in a serif, everything else in the theme sans | The serif marks "this is the verdict" the way a newspaper lede does. It is the typographic voice of the product. |
| The horizon strip (1 hour to 1 month) repeats on every asset | It is the identity motif: the same seven steps, the same glyphs, everywhere. |
| Direction uses glyphs in ink colour: ▲ ▼ ◆ | Green and red would be wrong: a rising USD/IDR is bad news for a rupiah holder, a rising IHSG is good. Shape carries direction, text carries meaning. |
| One accent, deep teal, on the selected horizon and the primary button only | Teal stays clear of the red, amber and green reserved for the watch level, so the accent never reads as a market signal. |
| Green and red appear on the two answer tags (now, next month) and on the watch level | Here colour means "good or not for you", never "price up or down": a rising USD/IDR is tagged red because the rupiah is weaker. Every tag carries its word, so colour is never the only signal. There is no middle answer by the owner's choice; the chance and its strength sit in the sentence under the tag. |
| The main row has four links; currencies and the track record sit in the footer | A newcomer needs the summary first. Reference pages stay reachable without competing with it. |
| Rules and whitespace separate sections; cards only for stock picks | A stock pick is a discrete item that can be compared and reordered. Sections of a brief are not. |
| Light mode only | The owner asked for one bright look everywhere; no dark mode or theme switch. |
| The summary is four cards with a chart each: price, now and next month, a 3-month line with the next-month cone, and the range | The owner found the text-heavy brief confusing. Reasons, sources and test results moved behind "Kenapa?" and "Data lain" on the detail page. |
| The asset page opens with today's live chart, then the forecast: conclusion, projection chart, and each technique's view | The owner wants the chart and the system's analysis first. Short-horizon detail, reasons and sources sit behind two collapsed sections. |
| A 1, 2 or 3-month filter sits directly above what it changes (summary cards, forecast) | One control per question, placed where its effect is seen. |
| Live candles are ink only: hollow for a rising minute, filled for a falling one | Green and red already mean good or bad for the owner; candles must not reuse them for up and down. |
| Technique paths use the first three slots of the validated categorical palette, each with its own dash pattern and an end label | Three lines pass the colour-blind checks together; dashes and labels mean colour is never the only cue. |
| Motion: hover and focus states only | Numbers that move on their own distract from reading them. Respects reduced motion by having none to reduce. |
| Astryx neutral theme as the base | Quiet defaults, accessible controls, and tokens that the few custom pieces reuse. |

## Honesty rules for the interface

- A percentage is always labelled as a chance, never as a promise.
- Every forecast shows whether it passed the historical test, in words.
- When data is stale or thin, the screen says so next to the number it affects.
- Empty lists stay empty and say why. No filler picks.
