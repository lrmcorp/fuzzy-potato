/* Simulasi modal: the owner types a capital, ARAH splits it across today's picks and shows the model's ranges in
   rupiah and percent for 1 week, 1, 2 and 3 months. */
import {useEffect, useMemo, useRef, useState} from 'react';
import {api, type SimResult} from './api';
import {useT} from './i18n';
import {Seg, Skeleton, Term, VerdictTag} from './ui';

const H = [{key: '1w', text: '1 mgg'}, {key: '1m', text: '1 bln'}, {key: '2m', text: '2 bln'}, {key: '3m', text: '3 bln'}];
const QUICK = [5e6, 10e6, 25e6, 50e6, 100e6];
const rp = (x: number) => `Rp ${Math.round(x).toLocaleString('id-ID')}`;
const srp = (x: number) => `${x > 0 ? '+' : x < 0 ? '−' : ''}${rp(Math.abs(x))}`;
const short = (x: number) => (x >= 1e9 ? `${(x / 1e9).toLocaleString('id-ID', {maximumFractionDigits: 1})} M` : `${(x / 1e6).toLocaleString('id-ID', {maximumFractionDigits: 0})} jt`);
const digits = (s: string) => Number(s.replace(/\D/g, '')) || 0;
const load = (k: string, d: string) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
const save = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

/** Portfolio value over time: modal today, then the middle line and the 9-in-10 band at each horizon. */
function FanChart({r, h}: {r: SimResult; h: string}) {
  const t = r.total!;
  // Drawn at the width it is shown, so labels stay 12px and dots stay round on a phone.
  const box = useRef<HTMLDivElement | null>(null);
  const [W, setW] = useState(640);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(Math.max(280, Math.round(el.clientWidth))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const Hh = 220, L = 8, R = 8, T = 16, B = 28;
  const pts = [{k: 'now', q05: r.capital, q50: r.capital, q95: r.capital}, ...r.horizons.map(k => ({k, ...t[k]}))];
  const lo = Math.min(...pts.map(p => p.q05)), hi = Math.max(...pts.map(p => p.q95));
  const pad = (hi - lo) * 0.08 || r.capital * 0.05;
  const x = (i: number) => L + (i / (pts.length - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - (lo - pad)) / (hi - lo + 2 * pad)) * (Hh - T - B);
  const band = `M${pts.map((p, i) => `${x(i)} ${y(p.q95)}`).join(' L')} L${[...pts].reverse().map((p, i) => `${x(pts.length - 1 - i)} ${y(p.q05)}`).join(' L')} Z`;
  const mid = `M${pts.map((p, i) => `${x(i)} ${y(p.q50)}`).join(' L')}`;
  const sel = pts.findIndex(p => p.k === h);
  return (
    <div ref={box}>
    <svg className="sim-chart" viewBox={`0 0 ${W} ${Hh}`} width={W} height={Hh} role="img"
      aria-label={`Nilai modal: hari ini ${rp(r.capital)}; ${H.find(x2 => x2.key === h)?.text} lagi tengah ${rp(t[h].q50)}, 9 dari 10 kemungkinan ${rp(t[h].q05)} sampai ${rp(t[h].q95)}`}>
      <line x1={L} x2={W - R} y1={y(r.capital)} y2={y(r.capital)} className="sim-base" />
      <path d={band} className="fc-b90" />
      <path d={mid} className="fc-med" />
      {pts.map((p, i) => (
        <g key={p.k}>
          <line x1={x(i)} x2={x(i)} y1={T} y2={Hh - B} className={i === sel ? 'sim-sel' : 'sim-tick'} />
          <circle cx={x(i)} cy={y(p.q50)} r={i === sel ? 6 : 4} fill="var(--ink)" />
          <text x={i === 0 ? x(i) : i === pts.length - 1 ? x(i) : x(i)} y={Hh - 8} textAnchor={i === 0 ? 'start' : i === pts.length - 1 ? 'end' : 'middle'}
            className={`fc-axis${i === sel ? ' strong' : ''}`}>{i === 0 ? 'Hari ini' : H.find(x2 => x2.key === p.k)?.text}</text>
        </g>
      ))}
    </svg>
    </div>
  );
}

function Change({from, to}: {from: number; to: number}) {
  const {pct} = useT();
  const d = to - from;
  return <span className={d > 0 ? 'chg-up' : d < 0 ? 'chg-down' : 'chg-flat'}>{srp(d)} ({pct((to / from - 1) * 100, 1)})</span>;
}

export function SimPage({onAuth}: {onAuth: () => void}) {
  const {num, pct} = useT();
  const [text, setText] = useState(() => load('arah.sim.modal', '10.000.000'));
  const [market, setMarket] = useState<'ID' | 'US'>(() => (load('arah.sim.market', 'ID') === 'US' ? 'US' : 'ID'));
  const [h, setH] = useState('1m');
  const [res, setRes] = useState<SimResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const capital = digits(text);

  // Recalculate shortly after typing stops, so the numbers follow the input without a button.
  useEffect(() => {
    if (capital <= 0) { setRes(null); return; }
    save('arah.sim.modal', text); save('arah.sim.market', market);
    const id = window.setTimeout(async () => {
      setBusy(true); setErr(null);
      try { setRes(await api.simulate(capital, market)); }
      catch (e) { if ((e as {status?: number}).status === 401) onAuth(); else setErr('Simulasi gagal dihitung. Coba lagi.'); }
      finally { setBusy(false); }
    }, 400);
    return () => window.clearTimeout(id);
  }, [capital, market]); // eslint-disable-line react-hooks/exhaustive-deps

  const t = res?.total?.[h];
  const maxCost = useMemo(() => Math.max(1, ...(res?.items ?? []).map(i => i.cost)), [res]);

  return (
    <>
      <header className="page-head">
        <h1 className="h1">Simulasi modal</h1>
        <p className="lead">Isi modal Anda. ARAH membaginya ke Pilihan ARAH hari ini dan menunjukkan kemungkinan nilainya nanti.</p>
      </header>

      <section className="card sim-input" aria-label="Modal">
        <label className="field sim-field">
          <span>Modal (Rp)</span>
          <input inputMode="numeric" value={text} aria-describedby="sim-hint"
            onChange={e => { const n = digits(e.target.value); setText(n ? n.toLocaleString('id-ID') : ''); }} />
        </label>
        <div className="chips" role="group" aria-label="Pilih cepat">
          {QUICK.map(q => (
            <button key={q} type="button" className="btn chip" aria-pressed={capital === q} onClick={() => setText(q.toLocaleString('id-ID'))}>{short(q)}</button>
          ))}
        </div>
        <div className="sim-opts">
          <Seg label="Bursa" value={market} onChange={v => setMarket(v as 'ID' | 'US')} options={[{key: 'ID', text: 'Saham Indonesia'}, {key: 'US', text: 'Saham Amerika'}]} />
          <span id="sim-hint" className="caption">
            Urutan saham: profil {res?.profile ?? 'sedang'} · <a href="#/pasar/pilihan">ubah</a>
          </span>
        </div>
      </section>

      {err && <p className="err" role="alert">{err}</p>}
      {!res ? (capital > 0 ? <div className="card"><Skeleton lines={5} /></div> : null)
        : res.items.length === 0 ? (
          <div className="card">
            <p className="body" style={{margin: 0}}>
              {res.need ? <>Modal belum cukup untuk 1 {market === 'ID' ? <Term k="lot">lot</Term> : 'lembar'} saham pilihan. Paling murah {res.need.key}: <b>{rp(res.need.rp)}</b>.</>
                : 'Hari ini belum ada saham yang lolos Pilihan ARAH. ARAH menunggu.'}
            </p>
          </div>
        ) : (
          <>
            <section className={`card sim-sum${busy ? ' busy' : ''}`} aria-live="polite" aria-label="Hasil simulasi">
              <div className="sim-sum-head">
                <h2 className="h3" style={{margin: 0}}>Nilai modal Anda</h2>
                <Seg label="Waktu" value={h} onChange={setH} options={H} />
              </div>
              {t && (
                <div className="sim-big">
                  <div>
                    <span className="caption">Kemungkinan tengah · {H.find(x => x.key === h)?.text} lagi</span>
                    <b className="sim-val">{rp(t.q50)}</b>
                    <Change from={res.capital} to={t.q50} />
                  </div>
                  <div>
                    <span className="caption">9 dari 10 kemungkinan</span>
                    <b className="sim-range">{rp(t.q05)} – {rp(t.q95)}</b>
                    <span className="caption">{pct((t.q05 / res.capital - 1) * 100, 1)} sampai {pct((t.q95 / res.capital - 1) * 100, 1)}</span>
                  </div>
                </div>
              )}
              {res.total && <FanChart r={res} h={h} />}
              <dl className="sim-facts">
                <div><dt>Dibelikan saham</dt><dd>{rp(res.invested ?? 0)}</dd></div>
                <div><dt>Sisa kas</dt><dd>{rp(res.cash)}</dd></div>
                <div><dt>Bila semua <Term k="rugi">batas rugi</Term> kena</dt><dd className="chg-down">{srp(-(res.loss_at_stops ?? 0))}</dd></div>
              </dl>
              {res.fx && <p className="caption" style={{margin: 0}}>Kurs USD/IDR {num(res.fx, 0)} dipakai untuk mengubah harga dolar ke rupiah.</p>}
            </section>

            <section className="card" aria-labelledby="sim-alloc">
              <h2 id="sim-alloc" className="h3" style={{marginTop: 0}}>Dibagi ke {res.items.length} saham</h2>
              <ul className="sim-list">
                {res.items.map(i => {
                  const o = i.outcomes[h];
                  return (
                    <li key={i.key} className="sim-row">
                      <div className="sim-row-top">
                        <a href={`#/a/${i.key}`} className="sim-name"><b>{i.key}</b> <span className="muted">{i.name}</span></a>
                        <VerdictTag tag={i.tag} />
                      </div>
                      <div className="sim-alloc-bar" aria-hidden="true"><span style={{width: `${(i.cost / maxCost) * 100}%`}} /></div>
                      <div className="sim-row-facts">
                        <span>{num(i.units, 0)} {i.unit} × {i.currency === 'IDR' ? rp(i.price) : `$${num(i.price, 2)}`} = <b>{rp(i.cost)}</b></span>
                        <span className="caption">{i.sector ?? '—'} · {pct((i.cost / res.capital) * 100, 0).replace('+', '')} dari modal</span>
                      </div>
                      {o && (
                        <div className="sim-row-out">
                          <span><span className="caption">Tengah {H.find(x => x.key === h)?.text}</span><br /><Change from={i.cost} to={o.q50} /></span>
                          <span><span className="caption">9 dari 10</span><br />{srp(o.q05 - i.cost)} s/d {srp(o.q95 - i.cost)}</span>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
            <p className="caption">
              Bukan janji keuntungan. Angka berasal dari simulasi model ARAH yang sama dengan grafik prakiraan, dihitung dari harga terakhir.
              Rentang total menjumlahkan batas tiap saham, jadi lebih lebar dari kenyataan bila saham tidak bergerak searah.
            </p>
          </>
        )}
    </>
  );
}
