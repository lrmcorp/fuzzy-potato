/* Pasar (redesign pack prompt 04, mockups Pasar.html and MobilePasar.html). */
import {Fragment, useState} from 'react';
import {api, type MarketRow, type RecCard, type Simple} from './api';
import {openAlertSheet} from './alertsheet';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {ChangeText, Icon, Seg, Skeleton, SourceLine, Sparkline, Term, VerdictTag} from './ui';
import type {RiskProfile} from './api';

const SEGS = [
  {key: 'pilihan', text: 'Pilihan ARAH'}, {key: 'saham', text: 'Saham'}, {key: 'indeks', text: 'Indeks'},
  {key: 'kurs', text: 'Kurs'}, {key: 'komoditas', text: 'Komoditas'},
];
const GROUP: Record<string, string> = {indeks: 'index', kurs: 'fx', komoditas: 'commodity'};

/** Rp 1,2 T / Rp 85 M per day, or $1,2 mlr / $350 jt; "—" when unknown. */
export function compact(x: number | null | undefined, cur: 'IDR' | 'USD' = 'IDR') {
  if (x == null || !isFinite(x) || x <= 0) return '—';
  const f = (v: number) => v.toLocaleString('id-ID', {maximumFractionDigits: v < 10 ? 1 : 0, minimumFractionDigits: 0});
  const [n, u]: [number, string] = cur === 'IDR'
    ? x >= 1e12 ? [x / 1e12, 'T'] : x >= 1e9 ? [x / 1e9, 'M'] : x >= 1e6 ? [x / 1e6, 'jt'] : [x, '']
    : x >= 1e9 ? [x / 1e9, 'mlr'] : x >= 1e6 ? [x / 1e6, 'jt'] : [x, ''];
  const body = `${f(n)}${u ? ' ' + u : ''}`;
  return cur === 'IDR' ? `Rp ${body}` : `$${body}`;
}

/** Smallest buy: 1 lot (100 shares) on IDX, 1 share in the US. */
function minCap(c: RecCard) {
  const cur = c.currency ?? (c.country === 'ID' ? 'IDR' : 'USD');
  const v = c.min_capital ?? c.price * (c.country === 'ID' ? 100 : 1);
  return cur === 'IDR' ? `Rp ${v.toLocaleString('id-ID', {maximumFractionDigits: 0})}`
    : `$${v.toLocaleString('id-ID', {maximumFractionDigits: 2, minimumFractionDigits: 2})}`;
}
const horizon = (c: RecCard) => `~${Math.max(1, Math.round((c.horizon_days ?? 31) / 30))} bln`;
const rrText = (c: RecCard, num: (x: number, d?: number) => string) => c.plan?.rr != null ? `1 : ${num(c.plan.rr, 1)}` : '—';

/** One line from the market's condition: how big a position the moment allows. */
function ContextChip({s}: {s: Simple | null | undefined}) {
  const {pct} = useT();
  const c = s?.indonesia;
  if (!c?.gauge) return null;
  const g = c.gauge.now;
  const tone = g < 0.4 ? 'orange' : g > 0.6 ? 'green' : 'grey';
  const advice = g < 0.4 ? 'masuk kecil' : g > 0.6 ? 'masuk normal' : 'masuk bertahap';
  return <span className={`ctx tag-${tone}`}>IHSG {pct(c.chg1m ?? 0, 1)} sebulan · {advice}</span>;
}

/** Trade plan on one line: stop, buy zone, "Kini", target 1 and target 2. */
function Ruler({c, mini}: {c: RecCard; mini?: boolean}) {
  const {num, range} = useT();
  const p = c.plan;
  const d = c.decimals;
  const lo = p.stop - (p.targets[1] - p.stop) * 0.08, hi = p.targets[1] + (p.targets[1] - p.stop) * 0.04;
  const x = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`;
  const w = (a: number, b: number) => `${((b - a) / (hi - lo)) * 100}%`;
  if (mini) return (
    <div className="mini-ruler" role="img" aria-label={`Batas rugi ${num(p.stop, d)}, kini ${num(c.price, d)}, target ${num(p.targets[0], d)}`}>
      <span className="ruler-track" style={{top: 0}} />
      <span className="ruler-risk" style={{top: 0, left: x(p.stop), width: w(p.stop, p.entry[0])}} />
      <span className="ruler-reward" style={{top: 0, left: x(c.price), width: w(c.price, p.targets[1])}} />
      <span className="ruler-tick" style={{top: -6, left: x(c.price), background: 'var(--ink)'}} />
    </div>
  );
  return (
    <div className="ruler" role="img" aria-label={`Batas rugi ${num(p.stop, d)}, beli ${range(p.entry[0], p.entry[1], d)}, kini ${num(c.price, d)}, target 1 ${num(p.targets[0], d)}, target 2 ${num(p.targets[1], d)}`}>
      <span className="ruler-track" />
      <span className="ruler-risk" style={{left: x(p.stop), width: w(p.stop, p.entry[0])}} />
      <span className="ruler-buy" style={{left: x(p.entry[0]), width: w(p.entry[0], p.entry[1])}} />
      <span className="ruler-reward" style={{left: x(p.entry[1]), width: w(p.entry[1], p.targets[1])}} />
      <span className="ruler-tick" style={{left: x(p.stop), background: 'var(--down)'}} />
      <span className="ruler-lbl" style={{left: x(p.stop), color: 'var(--down)'}}>Batas rugi</span>
      <span className="ruler-val" style={{left: x(p.stop)}}>{num(p.stop, d)}</span>
      <span className="ruler-tick" style={{left: x(c.price), background: 'var(--ink)', width: 3}} />
      <span className="ruler-lbl" style={{left: x(c.price)}}>Kini</span>
      <span className="ruler-buyl" style={{left: x((p.entry[0] + p.entry[1]) / 2)}}>beli {range(p.entry[0], p.entry[1], d)}</span>
      {p.targets.map((tg, i) => (
        <Fragment key={i}>
          <span className="ruler-tick" style={{left: x(tg), background: 'var(--up)'}} />
          <span className="ruler-lbl" style={{left: x(tg), color: 'var(--up)'}}>Target {i + 1}</span>
          <span className="ruler-val" style={{left: x(tg)}}>{num(tg, d)}</span>
        </Fragment>
      ))}
    </div>
  );
}

/** "Hitung lot": capital and risk in, lots out. The loss per share is the distance to the stop. */
function LotCalc({c}: {c: RecCard}) {
  const {num} = useT();
  const [cap, setCap] = useState('100.000.000');
  const [risk, setRisk] = useState('1');
  const capital = Number(cap.replace(/\D/g, ''));
  const r = Number(risk.replace(',', '.'));
  const perShare = c.price - c.plan.stop;
  const perLot = c.country === 'ID' ? 100 : 1;
  const lots = capital > 0 && r > 0 && perShare > 0 ? Math.floor((capital * r / 100) / (perShare * perLot)) : 0;
  const cost = lots * perLot * c.price;
  return (
    <div className="lot">
      <label className="field"><span>Modal (Rp)</span><input inputMode="numeric" value={cap} onChange={e => setCap(e.target.value)} /></label>
      <label className="field"><span>Risiko per transaksi (%)</span><input inputMode="decimal" value={risk} onChange={e => setRisk(e.target.value)} /></label>
      <p style={{margin: 0}} aria-live="polite">
        {lots > 0 ? <><output>{num(lots, 0)} {perLot === 100 ? 'lot' : 'lembar'}</output><br /><span className="caption">sekitar {num(cost, 0)}; rugi maks {num(capital * r / 100, 0)} bila batas rugi kena</span></>
          : <span className="caption">Isi modal dan risiko di atas nol.</span>}
      </p>
    </div>
  );
}

function PickActions({c, lot, setLot}: {c: RecCard; lot: boolean; setLot: (v: boolean) => void}) {
  return (
    <div className="chips" style={{alignItems: 'center'}}>
      <button type="button" className="btn btn-primary" onClick={() => openAlertSheet(c.key, {allPlan: true})}>Pasang 3 peringatan</button>
      <button type="button" className="btn" aria-expanded={lot} onClick={() => setLot(!lot)}>Hitung lot</button>
      <a className="btn btn-link" href={`#/a/${encodeURIComponent(c.key)}`} style={{fontWeight: 600}}>Detail {c.key}</a>
    </div>
  );
}

function PickRow({c, paused}: {c: RecCard; paused: boolean}) {
  const {num, pct, l} = useT();
  const [open, setOpen] = useState(false);
  const [lot, setLot] = useState(false);
  const has = !!c.plan;
  const t1 = has ? (c.plan.targets[0] / c.price - 1) * 100 : null;
  const loss = has ? (c.plan.stop / c.price - 1) * 100 : null;
  return (
    <>
      <tr>
        <td>
          <a href={`#/a/${encodeURIComponent(c.key)}`} style={{color: 'var(--ink)'}}><b className="row-title">{c.key}</b> <span className="muted">{c.name}</span></a>
          <span className="caption pick-sector">{c.sector ?? '—'}{c.held ? ' · pilihan sebelumnya' : ''}</span>
        </td>
        <td><VerdictTag tag={c.tag} paused={paused} /></td>
        <td className="num">{num(c.price, c.decimals)}</td>
        {has ? <><td className="num chg-up" style={{fontWeight: 600}}>{pct(t1, 1)}</td><td className="num chg-down" style={{fontWeight: 600}}>{pct(loss, 1)}</td><td className="num">{rrText(c, num)}</td></>
          : <td className="num muted" colSpan={3}>Rencana belum tersedia</td>}
        <td className="num">{minCap(c)}</td>
        <td className="num">{compact(c.liquidity, c.currency)}</td>
        <td style={{width: 48}}>
          <button type="button" className="icon-btn" aria-expanded={open} aria-label={`${open ? 'Tutup' : 'Buka'} rencana ${c.key}`} onClick={() => setOpen(!open)}>
            <Icon name="chevron" className="chev" />
          </button>
        </td>
      </tr>
      {open && (
        <tr className="expanded-row">
          <td colSpan={9}>
            {has ? (
              <div className="pick-expand">
                <div className="stack">
                  <Ruler c={c} />
                  <PickActions c={c} lot={lot} setLot={setLot} />
                  {lot && <LotCalc c={c} />}
                </div>
                <ul className="plus">{c.strengths.slice(0, 3).map((s, i) => <li key={i}>{l(s)}</li>)}</ul>
              </div>
            ) : <p className="body">Rencana belum tersedia</p>}
          </td>
        </tr>
      )}
    </>
  );
}

function PickCard({c, paused}: {c: RecCard; paused: boolean}) {
  const {num, pct, l} = useT();
  const [lot, setLot] = useState(false);
  const [why, setWhy] = useState(false);
  const has = !!c.plan;
  return (
    <article className="pcard">
      <div className="pcard-top">
        <a href={`#/a/${encodeURIComponent(c.key)}`} style={{color: 'var(--ink)'}}><b className="row-title">{c.key}</b> <span className="muted">{num(c.price, c.decimals)}</span></a>
        <VerdictTag tag={c.tag} paused={paused} />
      </div>
      <span className="caption">{c.sector ?? '—'}{c.held ? ' · pilihan sebelumnya' : ''}</span>
      {has ? (
        <>
          <p className="body" style={{margin: 0}}>Target 1 · {horizon(c)} <b className="chg-up">{pct((c.plan.targets[0] / c.price - 1) * 100, 1)}</b> · Rugi maks <b className="chg-down">{pct((c.plan.stop / c.price - 1) * 100, 1)}</b></p>
          <dl className="pick-facts">
            <div><dt>Modal 1 {c.country === 'ID' ? <Term k="lot">lot</Term> : 'lembar'}</dt><dd>{minCap(c)}</dd></div>
            <div><dt>Risiko : hasil</dt><dd>{rrText(c, num)}</dd></div>
            <div><dt>Transaksi/hari</dt><dd>{compact(c.liquidity, c.currency)}</dd></div>
          </dl>
          <Ruler c={c} mini />
          <button type="button" className="btn btn-primary btn-block" onClick={() => openAlertSheet(c.key, {allPlan: true})}>Pasang 3 peringatan</button>
          <div className="chips">
            <button type="button" className="btn" aria-expanded={lot} onClick={() => setLot(!lot)}>Hitung lot</button>
            <button type="button" className="btn" aria-expanded={why} onClick={() => setWhy(!why)}>Alasan</button>
            <a className="btn btn-link" href={`#/a/${encodeURIComponent(c.key)}`} style={{fontWeight: 600}}>Detail</a>
          </div>
          {lot && <LotCalc c={c} />}
          {why && <ul className="plus">{c.strengths.slice(0, 3).map((s, i) => <li key={i}>{l(s)}</li>)}</ul>}
        </>
      ) : <p className="body" style={{margin: 0}}>Rencana belum tersedia</p>}
    </article>
  );
}

/** How past picks ended: target 1, stop, or the month ran out. */
function PicksRecordLine({onAuth}: {onAuth: () => void}) {
  const r = useLoad(api.recs, [], onAuth).data?.record;
  if (!r) return null;
  if (r.closed < 5) return <span className="caption">Rekam jejak Pilihan ARAH belum cukup ({r.closed} selesai, {r.open} masih berjalan)</span>;
  return (
    <span className="caption">
      Rekam jejak Pilihan ARAH ({r.closed} terakhir): {r.target} kena target 1 · {r.stop} kena batas rugi · {r.expired} habis waktu
    </span>
  );
}

const MARKETS = [
  {key: 'ID' as const, title: 'Saham Indonesia', cur: 'IDR'},
  {key: 'US' as const, title: 'Saham Amerika', cur: 'USD'},
];

function Picks({onAuth, paused}: {onAuth: () => void; paused: boolean}) {
  const recs = useLoad(api.recs, [], onAuth);
  if (!recs.data) return <div className="card"><Skeleton lines={4} /></div>;
  const d = recs.data;
  const setProfile = async (p: RiskProfile) => { await api.setProfile(p); recs.reload(); };
  const profileBar = (
    <div className="profile-bar">
      <span className="caption">Urutan untuk profil risiko</span>
      <Seg label="Profil risiko" value={d.profile ?? 'sedang'} onChange={v => setProfile(v as RiskProfile)}
        options={[{key: 'hati-hati', text: 'Hati-hati'}, {key: 'sedang', text: 'Sedang'}, {key: 'berani', text: 'Berani'}]} />
    </div>
  );
  if (d.ID.length + d.US.length === 0) return <div className="card"><p className="body" style={{margin: 0}}>Hari ini belum ada saham yang lolos. ARAH menunggu.</p></div>;
  return (
    <>
      {profileBar}
      {MARKETS.map(m => {
        const list = d[m.key];
        const h = list[0] ? horizon(list[0]) : '~1 bln';
        return (
          <section key={m.key} className="stack" aria-labelledby={`picks-${m.key}`}>
            <h2 id={`picks-${m.key}`} className="picks-head">{m.title} <span className="caption">harga dalam {m.cur}</span></h2>
            {list.length === 0 ? <div className="card"><p className="body" style={{margin: 0}}>Belum ada saham {m.key === 'ID' ? 'Indonesia' : 'Amerika'} yang lolos hari ini.</p></div> : (
              <>
                <div className="card only-desk" style={{padding: 0, overflowX: 'auto'}}>
                  <table className="ptable">
                    <thead><tr>
                      <th>Saham</th><th>Status</th><th className="num">Harga ({m.cur})</th>
                      <th className="num"><Term k="target">Target 1</Term> · {h}</th><th className="num"><Term k="rugi">Rugi maks</Term></th><th className="num">Risiko : hasil</th>
                      <th className="num">Modal 1 {m.key === 'ID' ? <Term k="lot">lot</Term> : 'lembar'}</th><th className="num">Transaksi/hari</th><th />
                    </tr></thead>
                    <tbody>{list.map(c => <PickRow key={c.key} c={c} paused={paused} />)}</tbody>
                  </table>
                </div>
                <div className="pcards only-phone" style={{flexDirection: 'column'}}>{list.map(c => <PickCard key={c.key} c={c} paused={paused} />)}</div>
              </>
            )}
          </section>
        );
      })}
      <p className="caption">Transaksi/hari: rata-rata nilai transaksi 20 hari bursa terakhir. Risiko : hasil membandingkan jarak ke batas rugi dengan jarak ke target 1.</p>
    </>
  );
}

function QuoteRow({r, paused}: {r: MarketRow; paused: boolean}) {
  const {num} = useT();
  const stock = r.klass === 'stock';
  return (
    <li>
      <a className="wl-row" href={`#/a/${encodeURIComponent(r.key)}`}>
        <span className="wl-name"><strong>{stock ? r.key : r.name}</strong> <span className="muted">{stock ? r.name : r.name !== r.key ? r.key : ''}</span></span>
        <span className="wl-tag"><VerdictTag tag={r.tag} paused={paused && stock} /></span>
        <span className="wl-px">{num(r.price, r.price < 100 ? 2 : r.decimals)}<SourceLine src={r.src} className="caption src-line src-short" /></span>
        <span className="wl-chg"><ChangeText value={r.chg1d} upIsGood={(r.up_is ?? 1) >= 0} digits={2} /><span className="caption"> hari ini</span></span>
        <span className="wl-spark"><Sparkline values={r.spark.slice(-30)} label={`${r.key}: sebulan terakhir`} height={32} /><span className="caption">1 bln</span></span>
      </a>
    </li>
  );
}

function Quotes({group, onAuth, paused}: {group: string; onAuth: () => void; paused: boolean}) {
  const rows = useLoad(() => api.markets(group, '1m'), [group], onAuth);
  if (rows.error && !rows.data) return <div className="card"><p className="err">Data gagal dimuat. Coba lagi nanti.</p></div>;
  if (!rows.data) return <div className="card"><Skeleton lines={6} /></div>;
  const list = group.startsWith('stock') ? [...rows.data.rows].sort((a, b) => (b.score ?? -1) - (a.score ?? -1)) : rows.data.rows;
  if (list.length === 0) return <div className="card"><p className="body" style={{margin: 0}}>Data harga belum terunduh. ARAH mencoba lagi setiap jam.</p></div>;
  return <div className="card" style={{paddingTop: 'var(--s2)', paddingBottom: 'var(--s2)'}}><ul className="wl qrows">{list.map(r => <QuoteRow key={r.key} r={r} paused={paused} />)}</ul></div>;
}

export function MarketPage({onAuth, seg, paused}: {onAuth: () => void; seg: string; paused: boolean}) {
  const [mkt, setMkt] = useState<'ID' | 'US'>('ID');
  const b = useLoad(api.brief, [], onAuth);
  const current = SEGS.find(s => s.key === seg) ? seg : seg === 'saham-id' ? 'saham' : seg === 'saham-as' ? 'saham' : 'pilihan';
  return (
    <>
      <div className="p-head">
        <h1 className="h1">{current === 'pilihan' ? <><span className="only-desk">Pasar</span><span className="only-phone">Pilihan ARAH</span></> : 'Pasar'}</h1>
        <div className="filter" role="group" aria-label="Pilih pasar">
          {SEGS.map(s => (
            <button key={s.key} type="button" aria-pressed={current === s.key} onClick={() => { window.location.hash = `/pasar/${s.key}`; }}>{s.text}</button>
          ))}
        </div>
      </div>
      {current === 'pilihan' && <ContextChip s={b.data?.brief?.simple} />}
      {current === 'pilihan' && <PicksRecordLine onAuth={onAuth} />}
      {current === 'saham' && <Seg label="Bursa" value={mkt} onChange={v => setMkt(v as 'ID' | 'US')} options={[{key: 'ID', text: 'Indonesia'}, {key: 'US', text: 'Amerika'}]} />}
      {current === 'pilihan' ? <Picks onAuth={onAuth} paused={paused} />
        : current === 'saham' ? <Quotes key={mkt} group={mkt === 'ID' ? 'stock_id' : 'stock_us'} onAuth={onAuth} paused={paused} />
        : <Quotes key={current} group={GROUP[current]} onAuth={onAuth} paused={paused} />}
    </>
  );
}
