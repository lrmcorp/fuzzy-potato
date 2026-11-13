/* Ringkasan (redesign pack prompt 02, mockups Main.html and MobileHome.html). */
import {useState} from 'react';
import {api, type EventItem, type FlowRow, type PanelInfo, type PanelRow, type PulseInfo, type RecordInfo, type Simple, type SimpleCard} from './api';
import {compact} from './market';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {ChangeText, Mark, Seg, Skeleton, SourceLine, Sparkline, Term, VerdictTag} from './ui';
import type {Factor, RiskProfile} from './api';

const DIRTAG = {
  naik: {key: 'naik', label: 'Naik', icon: 'up', tone: 'green'},
  datar: {key: 'datar', label: 'Datar', icon: 'square', tone: 'grey'},
  turun: {key: 'turun', label: 'Turun', icon: 'down', tone: 'orange'},
  belum_jelas: {key: 'belum_jelas', label: 'Belum jelas arahnya', icon: 'square', tone: 'grey'},
} as const;
const H_LABEL: Record<string, string> = {'1m': '1 bln', '2m': '2 bln', '3m': '3 bln'};
// Foreign markets by the name of their index, the way the news writes them.
const INDEX_NAME: Record<string, string> = {SPX: 'S&P 500', N225: 'Nikkei 225', STI: 'STI', SSE: 'Shanghai Composite'};

function Gauge({now, next, h}: {now: number; next: number; h: string}) {
  // The "Sekarang" dot takes the colour of where it sits: pressing (orange), balanced (grey), supportive (green).
  const tone = now < 0.4 ? 'var(--down)' : now > 0.6 ? 'var(--up)' : 'var(--ink-2)';
  const pos = (x: number) => `${Math.round(Math.min(0.97, Math.max(0.03, x)) * 100)}%`;
  const word = (x: number) => (x < 0.4 ? 'menekan' : x > 0.6 ? 'mendukung' : 'seimbang');
  // Near either end a centred label would spill out of the card; anchor it to the dot's side instead.
  const edge = (x: number) => (x < 0.12 ? {transform: 'translateX(-8px)'} : x > 0.88 ? {transform: 'translateX(calc(-100% + 8px))'} : {});
  return (
    <div className="gauge" role="img" aria-label={`Sekarang ${word(now)}, ${H_LABEL[h]} lagi ${word(next)}`}>
      <div className="gauge-track" />
      <div className="gauge-mid" style={{left: '50%'}} />
      <div className="gauge-lbl" style={{left: pos(now), color: tone, ...edge(now)}}>Sekarang</div>
      <div className="gauge-dot" style={{left: pos(now), background: tone}} />
      <div className="gauge-dot hollow" style={{left: pos(next)}} />
      {/* When the two dots sit close together, the forecast label moves under the track so the labels never collide. */}
      <div className="gauge-lbl" style={{left: pos(next), ...edge(next), ...(Math.abs(now - next) < 0.15 ? {top: 38} : {})}}>{H_LABEL[h]}</div>
      <div className="gauge-end" style={{left: 0}}>Menekan</div>
      <div className="gauge-end" style={{right: 0}}>Mendukung</div>
    </div>
  );
}

const SIDE = {
  1: {word: 'Mendukung', icon: 'up', cls: 'chg-up'},
  [-1]: {word: 'Menekan', icon: 'down', cls: 'chg-down'},
  0: {word: 'Seimbang', icon: 'square', cls: 'chg-flat'},
} as Record<number, {word: string; icon: string; cls: string}>;

/** The factors behind the gauge, each with the way it pushes: the gauge is never a black box. */
function Factors({items, next, h}: {items: Factor[]; next?: number; h: string}) {
  const {pct} = useT();
  const model: Factor = {label: `Prakiraan model ${H_LABEL[h]}`, value: null, kind: 'pct',
    side: next == null ? null : next >= 0.6 ? 1 : next <= 0.4 ? -1 : 0};
  return (
    <ul className="factors" aria-label="Faktor yang menggerakkan arah pasar">
      {[...items, model].map(f => {
        const s = f.side == null ? null : SIDE[f.side];
        return (
          <li key={f.label}>
            <span>{f.label}{f.value != null && <span className="muted"> {f.kind === 'idr' ? compact(Math.abs(f.value)) : pct(f.value, 1)}</span>}</span>
            {s ? <span className={`${s.cls} factor-side`}><Mark icon={s.icon} />{s.word}</span> : <span className="muted">—</span>}
          </li>
        );
      })}
    </ul>
  );
}

const PROFILE_OPTS: {key: RiskProfile; text: string; hint: string}[] = [
  {key: 'hati-hati', text: 'Hati-hati', hint: 'rugi kecil dulu'},
  {key: 'sedang', text: 'Sedang', hint: 'seimbang'},
  {key: 'berani', text: 'Berani', hint: 'target besar dulu'},
];

/** One question, once: how much swing the owner can take. It only changes the order of the picks. */
function RiskQuestion({onDone}: {onDone: () => void}) {
  const [busy, setBusy] = useState(false);
  const pick = async (p: RiskProfile) => { setBusy(true); try { await api.setProfile(p); onDone(); } finally { setBusy(false); } };
  return (
    <section className="card risk-q" aria-labelledby="rq-h">
      <h2 id="rq-h" className="h3" style={{margin: 0}}>Kalau saham turun 10% seminggu setelah dibeli, Anda…</h2>
      <div className="risk-opts">
        {PROFILE_OPTS.map(o => (
          <button key={o.key} type="button" className="btn" disabled={busy} onClick={() => pick(o.key)}>
            <b>{o.text}</b><span className="caption">{o.key === 'hati-hati' ? 'gelisah, ingin jual' : o.key === 'sedang' ? 'tenang, menunggu' : 'beli lagi'}</span>
          </button>
        ))}
      </div>
      <p className="caption" style={{margin: 0}}>Jawaban ini hanya mengubah urutan Pilihan ARAH. Bisa diubah di Pasar.</p>
    </section>
  );
}

function MarketCard({c, title, h}: {c: SimpleCard; title: string; h: string}) {
  const {num} = useT();
  const fx = c.klass === 'fx';
  const d = c.price < 100 ? 2 : c.decimals;
  const rd = c.price >= 1000 ? 0 : d;  // ranges read faster without decimals: "4.606 sampai 6.091"
  const chg = c.chg1d ?? null;
  const fxWord = fx && chg != null && Math.abs(chg) >= 0.05 ? (chg > 0 ? 'rupiah melemah' : 'rupiah menguat') : undefined;
  const dir = c.next.dir ?? 'datar';
  return (
    <a className="mcard" href={`#/a/${encodeURIComponent(c.key)}`}>
      <div className="mcard-top">
        <span className="mcard-name">{title}</span>
        {fxWord && <span className={`caption ${chg! > 0 ? 'chg-down' : 'chg-up'}`} style={{fontWeight: 600}}>{fxWord}</span>}
      </div>
      <div className="mcard-val">{num(c.price, d)}</div>
      {/* Today and the last month side by side, each with its period, so the card never fights the headline. */}
      <div className="chg-pair">
        <span><ChangeText value={chg} upIsGood={(c.up_is ?? 1) >= 0} /> <span className="caption">hari ini</span></span>
        <span><ChangeText value={c.chg1m ?? null} upIsGood={(c.up_is ?? 1) >= 0} /> <span className="caption">1 bln</span></span>
      </div>
      <Sparkline values={c.spark ?? []} range={c.next.range} label={`${title}: 3 bulan terakhir dan prakiraan ${H_LABEL[h]}`} />
      <span className="caption spark-lbl">3 bln terakhir · prakiraan {H_LABEL[h]}</span>
      <div className="mcard-foot">
        <VerdictTag tag={DIRTAG[dir]} prefix={`${H_LABEL[h]}: `} />
      </div>
      {/* The odds come from the model: its 5th to 95th percentile, so 9 of 10 simulated paths end inside. */}
      <span className="rng caption">{c.next.odds ? `${c.next.odds.n} dari ${c.next.odds.of}` : '9 dari 10'} kemungkinan di {num(c.next.range[0], rd)}–{num(c.next.range[1], rd)}</span>
      <SourceLine src={c.src} />
    </a>
  );
}

function AbroadCard({s}: {s: NonNullable<Simple['abroad']>}) {
  const {t} = useT();
  const max = Math.max(...s.countries.map(c => Math.abs(c.chg1m ?? 0)), 1);
  return (
    <a className="mcard abroad" href="#/pasar/indeks">
      <div className="mcard-top"><span className="mcard-name">Bursa luar negeri</span><span className="caption">1 bln</span></div>
      <div className="mcard-abroad">
        {s.countries.map(c => {
          const v = c.chg1m ?? 0;
          return (
            <div key={c.key} className="ab-row">
              <span title={t(`c_${c.country}` as 'c_US')}>{INDEX_NAME[c.key] ?? c.name}</span>
              <div className="ab-bar" style={{justifyContent: v < 0 ? 'flex-end' : 'flex-start'}}>
                <span style={{width: `${Math.max(6, (Math.abs(v) / max) * 100)}%`, background: v < 0 ? 'var(--down-mark)' : 'var(--up)'}} />
              </div>
              <ChangeText value={v} />
            </div>
          );
        })}
      </div>
    </a>
  );
}

/** Net foreign flow: IHSG today as one number, then the stocks foreign investors bought and sold most. */
function ForeignCard({f}: {f: PanelInfo['foreign']}) {
  const net = f.day?.net_foreign ?? null;
  const max = Math.max(...[...f.buy, ...f.sell].map(r => Math.abs(r.net)), 1);
  const list = (rows: FlowRow[], buy: boolean) => (
    <ul className="flow-list" aria-label={buy ? 'Beli bersih asing terbesar' : 'Jual bersih asing terbesar'}>
      {rows.length === 0 ? <li className="muted">—</li> : rows.map(r => (
        <li key={r.key}>
          <a href={`#/a/${r.key}`}>{r.key}</a>
          <span className="flow-bar"><span style={{width: `${Math.max(6, (Math.abs(r.net) / max) * 100)}%`, background: buy ? 'var(--up)' : 'var(--down-mark)'}} /></span>
          <span className={buy ? 'chg-up' : 'chg-down'}>{compact(Math.abs(r.net))}</span>
        </li>
      ))}
    </ul>
  );
  return (
    <div className="mcard flow">
      <div className="mcard-top"><span className="mcard-name"><Term k="asing">Asing di IHSG</Term></span><span className="caption">hari ini</span></div>
      <span className={`mcard-val ${net == null ? '' : net >= 0 ? 'chg-up' : 'chg-down'}`}>
        {net == null ? '—' : `${net >= 0 ? 'Beli' : 'Jual'} ${compact(Math.abs(net))}`}
      </span>
      <div className="flow-cols">
        <div><span className="caption">Beli bersih · 1 bln</span>{list(f.buy, true)}</div>
        <div><span className="caption">Jual bersih · 1 bln</span>{list(f.sell, false)}</div>
      </div>
      <SourceLine src={f.source && f.at ? {source: f.source, at: f.at, delay_min: 0} : null} />
    </div>
  );
}

/** A short table of values with their one-month change; "—" where there is no feed. */
function ValueCard({title, rows, period}: {title: string; rows: PanelRow[]; period: string}) {
  const {num} = useT();
  // Several feeds in one card: the line shows the oldest of them, so the card never looks fresher than it is.
  const src = rows.map(r => r.src).filter((x): x is NonNullable<typeof x> => !!x).sort((x, y) => x.at - y.at)[0] ?? null;
  return (
    <div className="mcard vcard">
      <div className="mcard-top"><span className="mcard-name">{title}</span><span className="caption">{period}</span></div>
      <dl className="vrows">
        {rows.map(r => (
          <div key={r.key} className="vrow">
            <dt>{r.label}</dt>
            <dd className="num">{r.price == null ? '—' : `${num(r.price, r.decimals ?? 2)}${r.unit ?? ''}`}</dd>
            <dd className="num">{r.price == null ? <span className="muted">—</span> : <ChangeText value={r.chg1m} />}</dd>
          </div>
        ))}
      </dl>
      <SourceLine src={src} />
    </div>
  );
}

function Watchlist() {
  const {num} = useT();
  const w = useLoad(api.watchlist, []);
  return (
    <section className="card" aria-labelledby="wl-h">
      <div className="card-head">
        <h2 id="wl-h" className="h2" style={{fontWeight: 600}}>Pantauan saya</h2>
        <a className="btn" href="#/cari">Tambah saham</a>
      </div>
      {!w.data ? <Skeleton lines={3} /> : w.data.items.length === 0 ? (
        <div className="empty">
          <p className="body" style={{margin: 0}}>Belum ada saham dipantau.</p>
          <a className="btn btn-primary" href="#/pasar/pilihan">Ambil dari Pilihan ARAH</a>
        </div>
      ) : (
        <ul className="wl">
          {w.data.items.map(r => (
            <li key={r.key}>
              <a className="wl-row" href={`#/a/${encodeURIComponent(r.key)}`}>
                <span className="wl-name"><strong>{r.klass === 'stock' ? r.key : r.name}</strong>{' '}
                  <span className="muted">{r.klass === 'stock' ? r.name : r.alerts ? `${r.alerts} peringatan` : ''}</span></span>
                <span className="wl-tag"><VerdictTag tag={r.tag} /></span>
                <span className="wl-px">{r.price != null ? num(r.price, r.price < 100 ? 2 : r.decimals) : 'Tidak ada data'}</span>
                <span className="wl-chg"><ChangeText value={r.chg1d} upIsGood={r.up_is >= 0} digits={2} /><span className="caption"> hari ini</span></span>
                <span className="wl-spark"><Sparkline values={r.spark.slice(-30)} label={`${r.key}: sebulan terakhir`} height={32} /><span className="caption">1 bln</span></span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const COUNTRY: Record<string, string> = {ID: 'Indonesia', US: 'Amerika Serikat', JP: 'Jepang', SG: 'Singapura', CN: 'China', EU: 'Eropa', GB: 'Inggris'};
const wib = (ts: number, o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('id-ID', {...o, timeZone: 'Asia/Jakarta'}).format(ts * 1000);

/** Only what can move the owner's markets: high-impact releases, Indonesian events and dated news, today and
 *  tomorrow. When nothing qualifies, the section is not shown at all. */
function importantEvents(events: EventItem[]): EventItem[] {
  const now = Date.now() / 1000;
  const endTomorrow = (() => {
    const d = new Date(Date.now() + 7 * 3600 * 1000);  // Jakarta date
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 2) / 1000 - 7 * 3600;
  })();
  // Routine Indonesian dates (BPS, MSCI, IDX index changes, BI) are worth seeing three weeks ahead.
  return events
    .filter(e => e.at >= now - 3600 && (e.at < endTomorrow || (e.kind && e.at < now + 21 * 86400)))
    .filter(e => e.source === 'news' || e.country === 'ID' || !e.impact || e.impact === 'High')
    .slice(0, 6);
}

function Agenda({events}: {events: EventItem[]}) {
  const {l} = useT();
  const today = wib(Date.now() / 1000, {day: 'numeric'});
  return (
    <section className="card" aria-labelledby="ag-h">
      <h2 id="ag-h" className="h2" style={{fontWeight: 600, marginBottom: 'var(--s4)'}}>Agenda penting</h2>
      <ul className="agenda">
        {events.map((e, i) => {
          const isToday = wib(e.at, {day: 'numeric'}) === today;
          const isTomorrow = wib(e.at, {day: 'numeric'}) === wib(Date.now() / 1000 + 86400, {day: 'numeric'});
          const dayLabel = isToday ? 'Hari ini' : isTomorrow ? 'Besok' : wib(e.at, {weekday: 'short'});
          const big = e.source === 'news' ? '•' : e.timed === false ? wib(e.at, {day: 'numeric', month: 'short'}) : wib(e.at, {hour: '2-digit', minute: '2-digit'});
          return (
            <li key={i} className="ag-item">
              <span className="day"><small>{dayLabel}</small><b>{big}</b></span>
              <span className="ag-body">
                <span className="row-title">{e.title ?? l(e.what)}</span>
                <span className="muted">{COUNTRY[e.country] ?? e.country}{e.source === 'news' ? ' · dari berita' : e.note ? ` · ${e.note}` : ' · WIB'}</span>
                {(e.forecast || e.previous) && (
                  <span className="ag-nums">
                    {e.forecast && <>Perkiraan <b>{e.forecast.replace('.', ',')}</b></>}
                    {e.forecast && e.previous && ' · '}
                    {e.previous && <>Sebelumnya <b>{e.previous.replace('.', ',')}</b></>}
                  </span>
                )}
                {e.why && <span className="ag-why"><b>Kenapa penting:</b> {l(e.why)}</span>}
              </span>
            </li>
          );
        })}
      </ul>
      <p style={{margin: 'var(--s4) 0 0'}}><a href="#/berita" style={{fontWeight: 600}}>Kalender lengkap</a></p>
    </section>
  );
}

/** One market in one punch: the sentence, why in two short lines, and where to read more. */
function RecordLine({r}: {r?: RecordInfo}) {
  if (!r) return null;
  return (
    <span className="caption record">
      {r.enough ? `Prediksi 1 bln tepat ${r.pct}% (${r.n} prediksi terakhir)` : `Rekam jejak belum cukup (${r.n} dinilai, ${r.pending} menunggu 1 bln)`}
    </span>
  );
}

function MarketPunch({place, sentence, why, causes, news, asset, assetLabel, gauge, h, big, record, factors, children}: {
  place: React.ReactNode; sentence: string | null | undefined; why: string[]; causes: number; news: string; asset: string; assetLabel: string;
  gauge?: {now: number; next: number}; h: string; big?: boolean; record?: RecordInfo; factors?: Factor[]; children?: React.ReactNode}) {
  return (
    <div className={`punch${big ? ' big' : ''}`}>
      <div className="hero-text">
        <span className="caption">{place}</span>
        {big ? <h1 className="h1">{sentence}</h1> : <h2 className="h2">{sentence}</h2>}
        {why.length > 0 && <p className="why-line"><b>Kenapa:</b> {why.join(' ')}</p>}
        <p className="punch-links">
          <a href={news}>{causes ? `${causes} berita penyebab` : 'Berita penyebab'}</a>
          <a href={`#/a/${asset}`}>Lihat {assetLabel}</a>
        </p>
        <RecordLine r={record} />
      </div>
      <div className="gauge-box">
        {children}
        {gauge ? <Gauge now={gauge.now} next={gauge.next} h={h} /> : <Skeleton lines={1} />}
        {factors && <Factors items={factors} next={gauge?.next} h={h} />}
      </div>
    </div>
  );
}

export function HomePage({onAuth, pulse}: {onAuth: () => void; pulse: PulseInfo | null}) {
  const [h, setH] = useState('1m');
  const b = useLoad(api.brief, [], onAuth);
  const pn = useLoad(api.panel, [], onAuth);
  const other = useLoad(() => (h === '1m' ? Promise.resolve(null) : api.simple(h)), [h], onAuth);
  const brief = b.data?.brief;
  const simple: Simple | null | undefined = h === '1m' ? brief?.simple : other.data;
  const ind = simple?.indonesia;
  if (b.error && !brief) return <p className="err">Data gagal dimuat. Muat ulang halaman.</p>;
  if (!brief) return <><div className="card"><Skeleton lines={3} /></div><div className="card"><Skeleton lines={4} /></div></>;
  const causes = (c: string) => (brief.countries?.[c]?.events ?? []).length;
  const us = simple?.abroad?.countries.find(c => c.country === 'US');
  // Why: the analyst desk's own summary when the AI team ran, else the strongest reasons on the market's card.
  const whyOf = (c: string, card?: SimpleCard | null): string[] => {
    const desk = brief.countries?.[c]?.summary?.id;
    if (desk) return [desk.split(/(?<=\.)\s/)[0]];
    // Reasons that point the same way as the sentence come first: "tertekan" is explained by what presses.
    const g = card?.gauge?.now ?? 0.5;
    const want = g < 0.4 ? -1 : g > 0.6 ? 1 : 0;
    const up = (card?.up_is ?? 1) >= 0 ? 1 : -1;
    const score = (lean: number) => (want === 0 ? 0 : lean * up === want ? -1 : lean === 0 ? 0 : 1);
    // A reason pointing against the sentence is left out rather than shown second: it would read as a contradiction.
    return [...(card?.reasons ?? [])].filter(r => score(r.lean) <= 0).sort((x, y) => score(x.lean) - score(y.lean)).slice(0, 2).map(r => r.text.id);
  };
  const events = importantEvents([...(brief.events ?? [])].sort((a, c) => a.at - c.at));
  return (
    <>
      {pn.data && !pn.data.profile && <RiskQuestion onDone={pn.reload} />}
      <section className="card hero-stack" aria-label="Arah pasar hari ini">
        <MarketPunch place={<>Indonesia · <Term k="ihsg" /></>} big sentence={simple?.headline ?? brief.headline.id} why={whyOf('ID', ind)} causes={causes('ID')}
          news="#/berita/ID" asset="IHSG" assetLabel="IHSG" gauge={ind?.gauge} h={h} record={b.data?.record} factors={pn.data?.factors.ID}>
          <div className="gauge-head">
            <span>Arah pasar</span>
            <Seg label="Rentang prakiraan" value={h} onChange={setH} options={['1m', '2m', '3m'].map(k => ({key: k, text: H_LABEL[k]}))} />
          </div>
        </MarketPunch>
        {simple?.headline_us && (
          <MarketPunch place="Amerika Serikat" sentence={simple.headline_us} why={whyOf('US', us)} causes={causes('US')}
            news="#/berita/US" asset="SPX" assetLabel="S&P 500" gauge={us?.gauge} h={h} factors={pn.data?.factors.US} />
        )}
      </section>

      <section className="mcards" aria-label="Pasar utama">
        {simple?.indonesia && <MarketCard c={simple.indonesia} title="IHSG" h={h} />}
        {simple?.usd && <MarketCard c={simple.usd} title="USD/IDR" h={h} />}
        {simple?.cny && <MarketCard c={simple.cny} title="CNY/IDR" h={h} />}
      </section>

      <section className="ctx-cards" aria-label="Asing, luar negeri, komoditas dan makro">
        {simple?.abroad && <AbroadCard s={simple.abroad} />}
        {pn.data && <ForeignCard f={pn.data.foreign} />}
        {pn.data && <ValueCard title="Komoditas" rows={pn.data.commodities} period="harga · 1 bln" />}
        {pn.data && <ValueCard title="Makro" rows={pn.data.macro} period="nilai · 1 bln" />}
      </section>

      <div className={events.length ? 'home-grid' : ''}>
        <Watchlist />
        {events.length > 0 && <Agenda events={events} />}
      </div>
      {pulse?.state === 'paused' && <p className="caption">Data belum diperbarui lebih dari sehari: sinyal dijeda.</p>}
    </>
  );
}
