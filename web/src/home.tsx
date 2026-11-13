/* Ringkasan (redesign pack prompt 02, mockups Main.html and MobileHome.html). */
import {useState} from 'react';
import {api, type EventItem, type PulseInfo, type Simple, type SimpleCard} from './api';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {ChangeText, Seg, Skeleton, Sparkline, VerdictTag} from './ui';

const DIRTAG = {
  naik: {key: 'naik', label: 'Naik', icon: 'up', tone: 'green'},
  datar: {key: 'datar', label: 'Datar', icon: 'square', tone: 'grey'},
  turun: {key: 'turun', label: 'Turun', icon: 'down', tone: 'orange'},
} as const;
const H_LABEL: Record<string, string> = {'1m': '1 bln', '2m': '2 bln', '3m': '3 bln'};

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
      <div className="gauge-lbl" style={{left: pos(next), ...edge(next)}}>{H_LABEL[h]}</div>
      <div className="gauge-end" style={{left: 0}}>Menekan</div>
      <div className="gauge-end" style={{right: 0}}>Mendukung</div>
    </div>
  );
}

function MarketCard({c, title, h}: {c: SimpleCard; title: string; h: string}) {
  const {num, range} = useT();
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
        <span className="only-desk"><ChangeText value={chg} upIsGood={(c.up_is ?? 1) >= 0} label={fxWord ?? 'hari ini'} /></span>
      </div>
      <div className="mcard-val">{num(c.price, d)}</div>
      <span className="only-phone"><ChangeText value={chg} upIsGood={(c.up_is ?? 1) >= 0} label={fxWord?.replace('melemah', 'lemah').replace('menguat', 'kuat')} /></span>
      <Sparkline values={c.spark ?? []} range={c.next.range} label={`${title}: 3 bulan terakhir dan prakiraan ${H_LABEL[h]}`} />
      <div className="mcard-foot">
        <VerdictTag tag={DIRTAG[dir]} prefix={`${H_LABEL[h]}: `} />
        <span className="rng">{range(c.next.range[0], c.next.range[1], rd)}</span>
      </div>
    </a>
  );
}

function AbroadCard({s}: {s: NonNullable<Simple['abroad']>}) {
  const {t} = useT();
  const max = Math.max(...s.countries.map(c => Math.abs(c.chg1m ?? 0)), 1);
  return (
    <a className="mcard abroad" href="#/pasar/indeks">
      <div className="mcard-top"><span className="mcard-name">Bursa luar negeri</span><span className="muted">sebulan</span></div>
      <div className="mcard-abroad">
        {s.countries.map(c => {
          const v = c.chg1m ?? 0;
          return (
            <div key={c.key} className="ab-row">
              <span>{c.country === 'US' ? 'Amerika' : t(`c_${c.country}` as 'c_US')}</span>
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
                <ChangeText value={r.chg1d} upIsGood={r.up_is >= 0} digits={2} />
                <span className="wl-spark"><Sparkline values={r.spark.slice(-30)} label={`${r.key}: sebulan terakhir`} height={32} /></span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Agenda({events}: {events: EventItem[]}) {
  const {l, lang} = useT();
  const day = (ts: number) => ({
    w: new Intl.DateTimeFormat('id-ID', {weekday: 'short'}).format(ts * 1000),
    d: new Intl.DateTimeFormat('id-ID', {day: 'numeric'}).format(ts * 1000),
  });
  const list = events.slice(0, 3);
  return (
    <section className="card" aria-labelledby="ag-h">
      <h2 id="ag-h" className="h2" style={{fontWeight: 600, marginBottom: 'var(--s4)'}}>Agenda hari ini</h2>
      {list.length === 0 ? <p className="body">Tidak ada rilis besar hari ini.</p> : (
        <ul className="agenda">
          {list.map((e, i) => {
            const x = day(e.at);
            const country = {ID: 'Indonesia', US: 'Amerika Serikat', JP: 'Jepang', SG: 'Singapura', CN: 'China', EU: 'Eropa', GB: 'Inggris'}[e.country] ?? e.country;
            return (
              <li key={i}>
                <span className="day"><small>{x.w}</small><b>{x.d}</b></span>
                <span><span className="row-title">{e.title ? `${e.title.split(',')[0]} ${country}` : l(e.what)}</span><br />
                  <span className="muted">{e.why ? l(e.why).split('.')[0] : lang === 'id' ? 'Dari berita' : 'From the news'}</span></span>
              </li>
            );
          })}
        </ul>
      )}
      <p style={{margin: 'var(--s4) 0 0'}}><a href="#/berita" style={{fontWeight: 600}}>Kalender lengkap</a></p>
    </section>
  );
}

export function HomePage({onAuth, pulse}: {onAuth: () => void; pulse: PulseInfo | null}) {
  const [h, setH] = useState('1m');
  const b = useLoad(api.brief, [], onAuth);
  const other = useLoad(() => (h === '1m' ? Promise.resolve(null) : api.simple(h)), [h], onAuth);
  const brief = b.data?.brief;
  const simple: Simple | null | undefined = h === '1m' ? brief?.simple : other.data;
  const ind = simple?.indonesia;
  if (b.error && !brief) return <p className="err">Data gagal dimuat. Muat ulang halaman.</p>;
  if (!brief) return <><div className="card"><Skeleton lines={3} /></div><div className="card"><Skeleton lines={4} /></div></>;
  const causes = (brief.countries?.ID?.events ?? []).length;
  const events = [...(brief.events ?? [])].sort((a, c) => a.at - c.at);
  return (
    <>
      <section className="card hero" aria-label="Arah pasar hari ini">
        <div className="hero-text">
          <h1 className="h1">{simple?.headline ?? brief.headline.id}</h1>
          <a href="#/berita">{causes ? `Kenapa? ${causes} berita penyebab` : 'Kenapa? Lihat berita penyebab'}</a>
        </div>
        <div className="gauge-box">
          <div className="gauge-head">
            <span>Arah pasar</span>
            <Seg label="Rentang prakiraan" value={h} onChange={setH} options={['1m', '2m', '3m'].map(k => ({key: k, text: H_LABEL[k]}))} />
          </div>
          {ind?.gauge ? <Gauge now={ind.gauge.now} next={ind.gauge.next} h={h} /> : <Skeleton lines={1} />}
        </div>
      </section>

      <section className="mcards" aria-label="Pasar utama">
        {simple?.indonesia && <MarketCard c={simple.indonesia} title="IHSG" h={h} />}
        {simple?.usd && <MarketCard c={simple.usd} title="USD/IDR" h={h} />}
        {simple?.cny && <MarketCard c={simple.cny} title="CNY/IDR" h={h} />}
        {simple?.abroad && <AbroadCard s={simple.abroad} />}
      </section>

      <div className="home-grid">
        <Watchlist />
        <Agenda events={events} />
      </div>
      {pulse?.state === 'paused' && <p className="caption">Data belum diperbarui lebih dari sehari: sinyal dijeda.</p>}
    </>
  );
}
