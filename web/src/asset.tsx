/* Asset detail (redesign pack prompt 03, mockups Aset.html and MobileAset.html). */
import {useEffect, useMemo, useRef, useState} from 'react';
import {api, ApiError, type Forecast, type PulseInfo, type StockVerdict, type Technique} from './api';
import {openAlertSheet} from './alertsheet';
import {AskAnswer} from './cari';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {StoryList} from './news';
import {FlowPanel, HistoryPanel, LivePanel, TickerNews} from './pages';
import {ChangeText, Icon, Seg, Sheet, Skeleton, SourceLine, StaleChip, Term, toast} from './ui';

const H = [{key: '1m', text: '+1 bln'}, {key: '2m', text: '+2 bln'}, {key: '3m', text: '+3 bln'}];

/* ---------- Forecast chart: 6 months of history, then the 50% and 90% bands ---------- */

function niceTicks(lo: number, hi: number, n = 4): number[] {
  const span = hi - lo || 1;
  const raw = span / (n - 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) ?? raw;
  const start = Math.floor(lo / step) * step;
  return Array.from({length: n + 1}, (_, i) => start + i * step).filter(v => v >= lo - step * 0.3 && v <= hi + step * 0.3).slice(0, n);
}

/** Width of an element, so a chart can be drawn at the size it is shown and its 12px labels stay 12px. */
function useWidth<T extends HTMLElement>(fallback: number): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

function ForecastChart({f}: {f: Forecast}) {
  const {num} = useT();
  const [table, setTable] = useState(false);
  const [box, width] = useWidth<HTMLDivElement>(760);
  const d = f.s0 < 100 ? 2 : f.decimals;
  const hist = f.history.slice(-126);
  const band = f.conclusion.band;
  const last = band[band.length - 1];
  if (hist.length < 10 || !last) return <p className="body">Data belum cukup untuk prakiraan</p>;
  const narrow = width < 520;
  const W = Math.max(300, width), Hh = narrow ? 260 : 320, L = narrow ? 44 : 56, R = narrow ? 64 : 120, T = 16, B = 40;
  const n = hist.length, steps = last.step;
  // History takes the first 70% of the plot and the forecast the rest, so the bands are wide enough to read.
  const split = L + (W - L - R) * 0.7;
  const xs = (i: number) => (i <= n - 1 ? L + (i / (n - 1)) * (split - L) : split + ((i - (n - 1)) / steps) * (W - R - split));
  const vals = [...hist.map(p => p.c), last.q05, last.q95];
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.06;
  const y0 = lo - pad, y1 = hi + pad;
  const y = (v: number) => T + (1 - (v - y0) / (y1 - y0)) * (Hh - T - B);
  const ticks = niceTicks(y0, y1, 4);
  const nowX = xs(n - 1), s0 = hist[n - 1].c;
  const at = (k: 'q05' | 'q25' | 'q50' | 'q75' | 'q95') => [`M${nowX} ${y(s0)}`, ...band.map(b => `L${xs(n - 1 + b.step)} ${y(b[k])}`)].join(' ');
  const poly = (a: 'q05' | 'q25', b2: 'q95' | 'q75') =>
    `M${nowX} ${y(s0)} ${band.map(b => `L${xs(n - 1 + b.step)} ${y(b[b2])}`).join(' ')} ${[...band].reverse().map(b => `L${xs(n - 1 + b.step)} ${y(b[a])}`).join(' ')} Z`;
  const line = hist.map((p, i) => `${i ? 'L' : 'M'}${xs(i).toFixed(1)} ${y(p.c).toFixed(1)}`).join(' ');
  const month = new Intl.DateTimeFormat('id-ID', {month: 'short'}).format(hist[0].t * 1000);
  const endX = xs(n - 1 + steps);
  const kiniText = `Kini ${num(s0, d)}`;
  const kw = kiniText.length * 7 + 16;
  return (
    <>
      <div ref={box}>
      <svg className="fc-svg" viewBox={`0 0 ${W} ${Hh}`} width={W} height={Hh} role="img"
        aria-label={`Harga 6 bulan terakhir dan prakiraan ${f.horizon_name.id}: tengah ${num(last.q50, d)}, 9 dari 10 kemungkinan antara ${num(last.q05, d)} sampai ${num(last.q95, d)}`}>
        {ticks.map(v => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="fc-grid" />
            <text x={L - 10} y={y(v) + 4} textAnchor="end" className="fc-axis">{num(v, v < 100 ? 1 : 0)}</text>
          </g>
        ))}
        <path d={poly('q05', 'q95')} className="fc-b90" />
        <path d={poly('q25', 'q75')} className="fc-b50" />
        <path d={line} className="fc-price" />
        <path d={at('q50')} className="fc-med" />
        <line x1={nowX} x2={nowX} y1={T - 8} y2={Hh - B + 8} className="fc-today" />
        <circle cx={nowX} cy={y(s0)} r={4} fill="var(--ink)" />
        <g className="fc-kini" transform={`translate(${Math.max(L, nowX - kw - 10)} ${Math.max(T, y(s0) - 40)})`}>
          <rect width={kw} height={24} rx={6} /><text x={8} y={16}>{kiniText}</text>
        </g>
        <text x={endX + 8} y={y(last.q95) + 4} className="fc-lbl">{num(last.q95, d)}</text>
        {!narrow && <text x={endX + 8} y={y(last.q95) + 18} className="fc-lbl">batas atas</text>}
        <text x={endX + 8} y={y(last.q50) + 4} className="fc-lbl mid">{num(last.q50, d)}{narrow ? '' : ' tengah'}</text>
        <text x={endX + 8} y={y(last.q05) + 4} className="fc-lbl">{num(last.q05, d)}</text>
        {!narrow && <text x={endX + 8} y={y(last.q05) + 18} className="fc-lbl">batas bawah</text>}
        <text x={L} y={Hh - 12} className="fc-axis">{month}</text>
        <text x={nowX} y={Hh - 12} textAnchor="middle" className="fc-axis">Hari ini</text>
        <text x={endX} y={Hh - 12} textAnchor="end" className="fc-axis">{f.horizon === '1m' ? '+1 bln' : f.horizon === '2m' ? '+2 bln' : '+3 bln'}</text>
      </svg>
      </div>
      <div className="fc-legend">
        <span><i className="sw sw-50" />1 dari 2 kemungkinan</span>
        <span><i className="sw sw-90" />9 dari 10 kemungkinan</span>
        <button type="button" className="btn btn-link" aria-expanded={table} onClick={() => setTable(!table)}>{table ? 'Tutup tabel' : 'Lihat sebagai tabel'}</button>
      </div>
      {table && (
        <table className="fc-table">
          <thead><tr><th>Waktu</th><th>Batas bawah</th><th>Tengah</th><th>Batas atas</th></tr></thead>
          <tbody>
            <tr><td>Hari ini</td><td>{num(s0, d)}</td><td>{num(s0, d)}</td><td>{num(s0, d)}</td></tr>
            {band.filter((_, i) => i === Math.floor(band.length / 2) || i === band.length - 1).map(b => (
              <tr key={b.step}><td>+{b.step} hari bursa</td><td>{num(b.q05, d)}</td><td>{num(b.q50, d)}</td><td>{num(b.q95, d)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

/* ---------- Keputusan ---------- */

function Bar({label, short, value, max = 100, unit, shortUnit, tick, tickNote}: {label: string; short: string; value: number; max?: number; unit: string; shortUnit?: string; tick?: number; tickNote?: string}) {
  return (
    <div className="bar">
      <div className="bar-top">
        <span><span className="only-desk">{label}</span><span className="only-phone">{short}</span></span>
        <b><span className="only-desk">{unit}</span><span className="only-phone">{shortUnit ?? unit}</span></b>
      </div>
      <div className="bar-track" role="img" aria-label={`${label} ${unit}`}>
        <span className="bar-fill" style={{width: `${Math.max(0, Math.min(100, (value / max) * 100))}%`}} />
        {tick != null && <span className="bar-tick" style={{left: `${tick}%`}} />}
      </div>
      {tickNote && <p className="caption only-desk" style={{margin: '6px 0 0'}}>{tickNote}</p>}
    </div>
  );
}

function askWhy(v: StockVerdict | null): string {
  if (!v) return 'Kenapa arahnya begini?';
  return {masuk: 'Kenapa masuk?', bertahap: 'Kenapa bertahap?', tunggu: 'Kenapa tunggu?', hindari: 'Kenapa hindari?'}[v.verdict];
}

function TanyaChips({k, v, onAsk, analysing, onAnalyse}: {k: string; v: StockVerdict | null; onAsk: (q: string) => void; analysing: boolean; onAnalyse: () => void}) {
  const why = askWhy(v);
  const label = v ? v.label.id : '';
  return (
    <div>
      <p className="caption only-desk" style={{margin: '0 0 var(--s2)'}}>Tanya ARAH</p>
      <div className="chips tanya">
        <button type="button" className="chip-q" onClick={() => onAsk(`${k}: ${why.replace('?', '')} menurut ARAH${label ? ` (${label})` : ''}?`)}>{why}</button>
        <button type="button" className="chip-q" onClick={() => onAsk(`${k}: kapan sebaiknya jual? Sebutkan batas rugi dan target.`)}>Kapan jual?</button>
        <button type="button" className="chip-q" onClick={onAnalyse} disabled={analysing}>{analysing ? 'Tim AI sedang menganalisa…' : 'Analisa lengkap tim AI'}</button>
      </div>
    </div>
  );
}

function Keputusan({k, f, v, paused, onAsk, analysing, onAnalyse}: {k: string; f: Forecast | null; v: StockVerdict | null | undefined; paused: boolean;
  onAsk: (q: string) => void; analysing: boolean; onAnalyse: () => void}) {
  const stock = f?.klass === 'stock';
  const p = v?.p_up ?? f?.conclusion.p_up ?? null;
  const pct = p == null ? null : Math.round(p * 100);
  if (stock && v === undefined) return <section className="card"><Skeleton lines={5} /></section>;
  // Same rule as the server: a flat middle with a 9-in-10 range wider than 5% either way is "belum jelas".
  const wide = !!f && (f.conclusion.q95 / f.s0 - 1 > 0.05 || 1 - f.conclusion.q05 / f.s0 > 0.05);
  const dir = p == null ? null : p >= 0.6 ? {label: 'Naik', icon: 'up', tone: 'green' as const} : p <= 0.4 ? {label: 'Turun', icon: 'down', tone: 'orange' as const}
    : wide ? {label: 'Belum jelas arahnya', icon: 'square', tone: 'grey' as const} : {label: 'Datar', icon: 'square', tone: 'grey' as const};
  const tone = stock ? v?.tone : dir?.tone;
  return (
    <section className="card" aria-labelledby="kp-h">
      <h2 id="kp-h" className="h2">{stock ? 'Keputusan' : 'Prakiraan 1 bulan'}</h2>
      <div className={`vblock tone-${tone ?? 'grey'}${paused ? ' paused' : ''}`}>
        {paused ? (
          <><p className="vword">Sinyal dijeda</p><p className="vsent">Data belum diperbarui lebih dari sehari.</p></>
        ) : stock && v ? (
          <><p className="vword"><VerdictMark icon={v.icon} />{v.label.id}</p><p className="vsent">{v.sentence}</p></>
        ) : stock ? (
          <><p className="vword">Tunggu</p><p className="vsent">Data belum cukup untuk memutuskan.</p></>
        ) : dir ? (
          <><p className="vword"><VerdictMark icon={dir.icon} />{dir.label}</p>
            <p className="vsent">{wide && dir.label.startsWith('Belum') ? 'Rentang 1 bulan terlalu lebar untuk menyebut arah.' : `ARAH memperkirakan ${dir.label.toLowerCase()} dalam 1 bulan.`}</p></>
        ) : <p className="vsent">Data belum cukup untuk prakiraan</p>}
      </div>
      <div className="bars">
        {stock && v?.score != null && <Bar label="Kondisi teknikal" short="Teknikal" value={v.score} unit={`${v.score} dari 100`} shortUnit={`${v.score}`} />}
        {pct != null && (
          <Bar label="Peluang naik 1 bln" short="Naik 1 bln" value={pct} unit={`${pct}%`} tick={60} tickNote={stock ? 'Perlu 60% untuk "Masuk"' : 'Di atas 60%: naik. Di bawah 40%: turun.'} />
        )}
      </div>
      {stock && <TanyaChips k={k} v={v ?? null} onAsk={onAsk} analysing={analysing} onAnalyse={onAnalyse} />}
    </section>
  );
}

function VerdictMark({icon}: {icon: string}) {
  return <span aria-hidden="true" style={{display: 'inline-flex'}}><svg width="16" height="16" viewBox="0 0 10 10">
    {icon === 'full' && <circle cx="5" cy="5" r="4.5" fill="currentColor" />}
    {icon === 'half' && <><circle cx="5" cy="5" r="4" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M5 1a4 4 0 0 0 0 8z" fill="currentColor" /></>}
    {icon === 'square' && <rect x="1" y="1" width="8" height="8" fill="currentColor" />}
    {icon === 'up' && <path d="M5 1l4.5 8h-9z" fill="currentColor" />}
    {icon === 'down' && <path d="M5 9L.5 1h9z" fill="currentColor" />}
  </svg></span>;
}

/* ---------- Cara ARAH menyimpulkan ---------- */

function TechRow({x, d, used}: {x: Technique; d: number; used: boolean}) {
  const {l, num} = useT();
  const [open, setOpen] = useState(false);
  const vote = x.vote > 0 ? {t: 'Naik', i: 'up', c: 'chg-up'} : x.vote < 0 ? {t: 'Turun', i: 'down', c: 'chg-down'} : {t: 'Datar', i: 'square', c: ''};
  const acc = x.key === 'sim' ? 'Dasar kisaran'
    : x.hist && x.hist.hit != null && x.hist.chance != null && x.hist.n_eff >= 12 ? `Benar ${Math.round(x.hist.hit * 100)}%, kebetulan ${Math.round(x.hist.chance * 100)}%`
    : x.weight ? `Bobot ${Math.round(x.weight * 100)}%` : 'Belum teruji';
  return (
    <li>
      <button type="button" className={`tech-row${used ? ' used' : ''}`} aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="tech-name">{l(x.name)}</span>
        <span className={vote.c} style={{display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600}}><VerdictMark icon={vote.i} />{vote.t}</span>
        <span className="t-target">{x.target != null ? num(x.target, d) : 'Tidak ada angka'}</span>
        <span className="t-acc">{acc}</span>
        <Icon name="chevron" className="chev" />
      </button>
      {open && (
        <div className="tech-body">
          <p style={{margin: 0}}><b>Kata teknik ini:</b> {l(x.reason)}</p>
          <p style={{margin: 0}}><b>Kenapa teknik ini:</b> {l(x.purpose)}</p>
          <p className="caption" style={{margin: 0}}>{l(x.status)}</p>
        </div>
      )}
    </li>
  );
}

function TechList({f, k}: {f: Forecast; k: string}) {
  const [all, setAll] = useState(false);
  const d = f.s0 < 100 ? 2 : f.decimals;
  const used = f.techniques.filter(x => x.status.used);
  const unused = f.techniques.filter(x => !x.status.used);
  // The best comparison: the unused technique whose history came closest to beating chance.
  const best = [...unused].sort((a, b) => ((b.hist?.hit ?? 0) - (b.hist?.chance ?? 0)) - ((a.hist?.hit ?? 0) - (a.hist?.chance ?? 0)))[0];
  const rest = unused.filter(x => x !== best);
  return (
    <>
      <p className="body">{used.length} dari {f.techniques.length} teknik ikut menentukan. Sisanya tidak lebih baik dari kebetulan di {k}.</p>
      <ul className="tech">
        {used.map(x => <TechRow key={x.key} x={x} d={d} used />)}
        {best && <TechRow x={best} d={d} used={false} />}
        {all && rest.map(x => <TechRow key={x.key} x={x} d={d} used={false} />)}
      </ul>
      {rest.length > 0 && (
        <button type="button" className="btn btn-link" style={{marginTop: 'var(--s3)', fontWeight: 600}} aria-expanded={all} onClick={() => setAll(!all)}>
          {all ? 'Sembunyikan teknik lain' : `Tampilkan ${rest.length} teknik lain`}
        </button>
      )}
    </>
  );
}

function Detail({k, onAuth}: {k: string; onAuth: () => void}) {
  const {l} = useT();
  const v = useLoad(() => api.asset(k, '1w'), [k], onAuth);
  if (!v.data) return <Skeleton lines={4} />;
  const view = v.data;
  return (
    <div className="stack">
      <ul className="plus" style={{gap: 'var(--s2)'}}>{view.reasons.slice(0, 5).map((r, i) => <li key={i}>{l(r.text)}</li>)}</ul>
      {view.watch && <p className="body"><b>Yang perlu diawasi:</b> {l(view.watch)}</p>}
      {view.sources && view.sources.length > 0 && (
        <StoryList items={view.sources.map((s2, i) => ({id: String(i), topic: '', country: '', title: s2.title, source: s2.source, url: s2.url, published_at: 0, outlets: 1}))} empty="" />
      )}
    </div>
  );
}

/** "▲ +50 (+1,57%) hari ini": the move in price units first, then in percent. */
function DayChange({abs, pct, d, upIsGood}: {abs: number | null; pct: number | null; d: number; upIsGood: boolean}) {
  const {num, pct: fp} = useT();
  if (abs == null || pct == null) return <ChangeText value={pct} upIsGood={upIsGood} label="hari ini" digits={2} />;
  const good = abs >= 0 ? upIsGood : !upIsGood;
  return (
    <span className={`chg ${abs === 0 ? 'chg-flat' : good ? 'chg-up' : 'chg-down'}`}>
      {abs !== 0 && <VerdictMark icon={abs > 0 ? 'up' : 'down'} />}{abs > 0 ? '+' : abs < 0 ? '\u2212' : ''}{num(Math.abs(abs), d)} ({fp(pct, 2)}) hari ini
    </span>
  );
}

/* ---------- Page ---------- */

export function AssetView({onAuth, k, pulse, onPulse}: {onAuth: () => void; k: string; pulse: PulseInfo | null; onPulse: () => void}) {
  const {num} = useT();
  const [h, setH] = useState('1m');
  const [tab, setTab] = useState('cara');
  const [more, setMore] = useState<'' | '1d' | '1y' | '5y'>('');
  const [question, setQuestion] = useState<string | null>(null);
  const [askOpen, setAskOpen] = useState(false);
  const [analysing, setAnalysing] = useState(false);
  const [watched, setWatched] = useState(false);
  const fc = useLoad(() => api.forecast(k, h), [k, h], onAuth);
  const live = useLoad(() => api.live(k), [k]);
  const [verdict, setVerdict] = useState<StockVerdict | null | undefined>(undefined);
  const f = fc.data;
  const stock = f?.klass === 'stock';
  const paused = pulse?.state === 'paused';
  useEffect(() => {
    if (!f) return;
    if (f.klass !== 'stock') { setVerdict(null); return; }
    api.verdict(k).then(setVerdict).catch(() => setVerdict(null));
  }, [k, f?.klass]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.watchlist().then(w => setWatched(w.items.some(x => x.key === k))).catch(() => undefined); }, [k]);

  const toggleWatch = async () => {
    const on = !watched;
    setWatched(on);
    try {
      await api.watch(k, on);
      toast({text: on ? (stock ? `${k} dipantau. Anda dikabari saat keputusan ARAH berubah.` : `${k} dipantau.`) : `${k} tidak dipantau lagi.`});
    } catch { setWatched(!on); }
  };
  const analyse = async () => {
    setAnalysing(true);
    try { await api.analyze(k); fc.reload(); toast({text: 'Analisa tim AI selesai. Lihat tab Cara ARAH menyimpulkan.'}); }
    catch (e) { toast({text: e instanceof ApiError && e.status === 409 ? 'Tim AI belum aktif.' : 'Tim AI belum bisa menganalisa. Coba lagi.'}); }
    finally { setAnalysing(false); }
  };
  const ask = (q: string) => { setQuestion(q); setAskOpen(false); };

  const name = f?.name ?? k;
  const d = f ? (f.s0 < 100 ? 2 : f.decimals) : 0;
  const px = live.data?.last ?? f?.s0 ?? null;
  const chgPct = live.data?.chg_pct ?? null;
  const chgAbs = live.data && live.data.prev ? live.data.last - live.data.prev : null;
  // Broker and foreign flow exist only for Indonesian stocks and indices (from Stockbit).
  const flow = !!f && f.country === 'ID' && (f.klass === 'stock' || f.klass === 'index');
  const tabs = useMemo(() => [
    {key: 'cara', text: 'Cara ARAH menyimpulkan'},
    ...(flow ? [{key: 'bandar', text: 'Bandar & asing'}] : []),
    {key: 'berita', text: 'Berita'}, {key: 'detail', text: 'Detail'},
  ], [f, flow]);

  if (fc.error && !f) return (
    <>
      <a className="back" href="#/pasar"><Icon name="back" size={18} />Pasar</a>
      <p className="body">{fc.error instanceof ApiError && fc.error.status === 404 ? `${k} tidak ditemukan.` : 'Data belum cukup untuk prakiraan'}</p>
    </>
  );

  return (
    <>
      <div className="phone-top">
        <a className="icon-btn" href="#/pasar" aria-label="Kembali ke Pasar"><Icon name="back" /></a>
        <StaleChip pulse={pulse} onChanged={onPulse} />
      </div>
      <a className="back only-desk" href="#/pasar"><Icon name="back" size={18} />Pasar</a>
      <header className="a-head">
        <div>
          <div className="a-title"><h1 className="h1">{stock ? k : name}</h1>{stock && <span className="muted row-title" style={{fontWeight: 400}}>{name}</span>}</div>
          <div className="a-price">
            <span className="px">{px != null ? `${f?.unit ? `${f.unit} ` : ''}${num(px, d)}` : 'Memuat harga…'}</span>
            <span className="only-desk"><DayChange abs={chgAbs} pct={chgPct} d={d} upIsGood={(f?.up_is ?? 1) >= 0} /></span>
            <span className="only-phone"><ChangeText value={chgPct} upIsGood={(f?.up_is ?? 1) >= 0} digits={2} /></span>
            {stock && f?.country === 'ID' && <span className="caption"><Term k="arb">Batas ARA/ARB</Term></span>}
          </div>
          <SourceLine src={live.data ? {source: live.data.source === 'stockbit' ? 'Stockbit' : live.data.source === 'binance' ? 'Binance' : live.data.source === 'daily' ? 'Penutupan harian' : 'Yahoo',
            at: live.data.at, delay_min: live.data.realtime ? 0 : (live.data.delay_min ?? 15)} : null} />
        </div>
        <div className="a-actions only-desk">
          <button type="button" className={`btn${watched ? ' star-on' : ''}`} aria-pressed={watched} onClick={toggleWatch}><Icon name="star" />{watched ? 'Dipantau' : 'Pantau'}</button>
          <button type="button" className="btn btn-primary" onClick={() => openAlertSheet(k, {allPlan: true})}><Icon name="bell" />Pasang peringatan</button>
        </div>
      </header>

      <div className="a-grid">
        <Keputusan k={k} f={f} v={stock ? verdict : null} paused={paused} onAsk={ask} analysing={analysing} onAnalyse={analyse} />
        <section className="card" aria-labelledby="fc-h">
          <div className="fc-head">
            <h2 id="fc-h" className="h2" style={{fontWeight: 600}}><span className="only-desk">6 bulan terakhir + prakiraan</span><span className="only-phone">Prakiraan</span></h2>
            <Seg label="Rentang prakiraan" value={h} onChange={setH} options={H} />
          </div>
          {f ? <ForecastChart f={f} /> : <Skeleton lines={6} />}
          <details className="more-ranges" open={!!more} onToggle={e => { if (!(e.target as HTMLDetailsElement).open) setMore(''); }}>
            <summary>Lainnya</summary>
            <div className="stack" style={{marginTop: 'var(--s3)'}}>
              <Seg label="Rentang grafik" value={more} onChange={x => setMore(x as typeof more)}
                options={[{key: '1d', text: 'Hari ini'}, {key: '1y', text: '1T'}, {key: '5y', text: '5T'}]} />
              {more === '1d' && <LivePanel k={k} decimals={d} klass={f?.klass ?? ''} />}
              {(more === '1y' || more === '5y') && <HistoryPanel k={k} range={more} klass={f?.klass ?? ''} onAuth={onAuth} />}
            </div>
          </details>
        </section>
      </div>
      {question && <AskAnswer question={question} />}

      <section className="card" aria-label="Rincian">
        <div className="tabs-u" role="group" aria-label="Rincian">
          {tabs.map(x => <button key={x.key} type="button" aria-pressed={tab === x.key} onClick={() => setTab(x.key)}>{x.text}</button>)}
        </div>
        {tab === 'cara' && (f ? <TechList f={f} k={k} /> : <Skeleton lines={4} />)}
        {tab === 'bandar' && <FlowPanel k={k} />}
        {tab === 'berita' && <TickerNews k={k} onAuth={onAuth} />}
        {tab === 'detail' && <Detail k={k} onAuth={onAuth} />}
      </section>

      <div className="actionbar">
        <button type="button" className={`btn${watched ? ' star-on' : ''}`} aria-pressed={watched} aria-label={watched ? 'Berhenti memantau' : 'Pantau'} onClick={toggleWatch}><Icon name="star" size={24} /></button>
        <button type="button" className="btn btn-primary" onClick={() => openAlertSheet(k, {allPlan: true})}>Pasang peringatan</button>
        <button type="button" className="btn" onClick={() => setAskOpen(true)}>Tanya</button>
      </div>
      {askOpen && (
        <Sheet title={`Tanya ARAH soal ${k}`} onClose={() => setAskOpen(false)}>
          <TanyaChips k={k} v={verdict ?? null} onAsk={ask} analysing={analysing} onAnalyse={() => { setAskOpen(false); void analyse(); }} />
          <AskFree k={k} onAsk={ask} />
        </Sheet>
      )}
    </>
  );
}

function AskFree({k, onAsk}: {k: string; onAsk: (q: string) => void}) {
  const [q, setQ] = useState('');
  return (
    <form className="stack" onSubmit={e => { e.preventDefault(); if (q.trim().length >= 3) onAsk(`${k}: ${q.trim()}`); }}>
      <label className="field"><span>Pertanyaan lain</span><input value={q} onChange={e => setQ(e.target.value)} placeholder={`mis. Apakah ${k} masih murah?`} /></label>
      <button type="submit" className="btn btn-primary btn-block" disabled={q.trim().length < 3}>Tanya</button>
    </form>
  );
}
