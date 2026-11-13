/* Kurs: one dollar and one yuan in rupiah, a converter, whether this month's move is normal, and why it moved. */
import {useState} from 'react';
import {api, type KursInfo, type KursRate} from './api';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {compact} from './market';
import {ChangeText, Mark, Seg, Skeleton, SourceLine, Sparkline} from './ui';

const PERIODS: [keyof KursRate['chg'], string][] = [['1d', 'hari ini'], ['1w', '1 mgg'], ['1m', '1 bln'], ['3m', '3 bln'], ['1y', '1 thn']];
const NORMAL_TONE: Record<string, 'green' | 'grey' | 'orange'> = {biasa: 'green', besar: 'grey', tidak_biasa: 'orange'};
const rp = (x: number, d = 0) => `Rp ${x.toLocaleString('id-ID', {maximumFractionDigits: d, minimumFractionDigits: d})}`;
const digits = (s: string) => Number(s.replace(/\./g, '').replace(',', '.').replace(/[^\d.]/g, '')) || 0;

/** Two-way converter: foreign amount to rupiah and back. */
function Converter({rate, cur}: {rate: number; cur: string}) {
  const [fx, setFx] = useState('100');
  const [idr, setIdr] = useState(() => Math.round(100 * rate).toLocaleString('id-ID'));
  return (
    <div className="conv">
      <label className="field"><span>{cur}</span>
        <input inputMode="decimal" value={fx} onChange={e => { setFx(e.target.value); setIdr(Math.round(digits(e.target.value) * rate).toLocaleString('id-ID')); }} />
      </label>
      <span className="conv-eq" aria-hidden="true">=</span>
      <label className="field"><span>Rupiah</span>
        <input inputMode="numeric" value={idr} onChange={e => {
          const n = Number(e.target.value.replace(/\D/g, '')) || 0;
          setIdr(n ? n.toLocaleString('id-ID') : '');
          setFx((n / rate).toLocaleString('id-ID', {maximumFractionDigits: 2}));
        }} />
      </label>
    </div>
  );
}

/** Where this month's change sits against the usual monthly move: ±1 usual is normal, ±2 large, beyond unusual. */
function NormalBar({chg, sd}: {chg: number; sd: number}) {
  const {pct} = useT();
  const span = Math.max(3 * sd, Math.abs(chg) * 1.15);
  const x = (v: number) => `${50 + (v / span) * 50}%`;
  const w = (a: number) => `${(a / span) * 50}%`;
  return (
    <div className="nbar" role="img" aria-label={`Perubahan sebulan ${pct(chg, 1)}; biasanya sekitar ${pct(sd, 1).replace('+', '')} ke atas atau ke bawah`}>
      <div className="nbar-track">
        <span className="nbar-z2" style={{left: x(-2 * sd), width: w(4 * sd)}} />
        <span className="nbar-z1" style={{left: x(-sd), width: w(2 * sd)}} />
        <span className="nbar-mid" />
        <span className="nbar-mark" style={{left: x(chg)}} />
      </div>
      <div className="nbar-lbls">
        <span style={{left: x(-sd)}}>{pct(-sd, 1)}</span>
        <span style={{left: '50%'}}>0</span>
        <span style={{left: x(sd)}}>{pct(sd, 1)}</span>
      </div>
      <div className="nbar-legend caption"><i className="sw nb1" />wajar <i className="sw nb2" />lebih besar dari biasa <i className="sw nb3" />tidak biasa</div>
    </div>
  );
}

function YearBar({r}: {r: KursRate}) {
  const {num} = useT();
  const pos = r.year.pos ?? 0.5;
  return (
    <div className="ybar" role="img" aria-label={`Setahun terakhir: terendah ${num(r.year.lo, 0)}, tertinggi ${num(r.year.hi, 0)}, sekarang ${num(r.price, 0)}`}>
      <div className="ybar-track"><span className="ybar-dot" style={{left: `${Math.min(98, Math.max(2, pos * 100))}%`}} /></div>
      <div className="ybar-ends"><span>Terendah {num(r.year.lo, 0)}</span><span>Tertinggi {num(r.year.hi, 0)}</span></div>
    </div>
  );
}

const PUSH = {
  1: {icon: 'up', cls: 'chg-down', text: 'mendorong dolar naik'},
  [-1]: {icon: 'down', cls: 'chg-up', text: 'menahan dolar'},
  0: {icon: 'square', cls: 'chg-flat', text: 'netral'},
} as Record<number, {icon: string; cls: string; text: string}>;

function Drivers({k}: {k: KursInfo}) {
  const {pct, num} = useT();
  const max = Math.max(...k.peers.map(p => Math.abs(p.chg1m)), 0.5);
  return (
    <>
      <h3 className="hero-sub">Rupiah dan mata uang Asia terhadap dolar · 1 bln</h3>
      <ul className="peers" aria-label="Perubahan sebulan terhadap dolar; positif berarti mata uang itu melemah">
        {k.peers.map(p => (
          <li key={p.key} className={p.key === 'USDIDR' ? 'me' : ''}>
            <span>{p.name}</span>
            <span className="peer-bar"><span style={{
              [p.chg1m >= 0 ? 'left' : 'right']: '50%', width: `${(Math.abs(p.chg1m) / max) * 50}%`,
              background: p.chg1m > 0 ? 'var(--down-mark)' : 'var(--up)'}} /></span>
            <span className={p.chg1m > 0 ? 'chg-down' : 'chg-up'}>{p.chg1m > 0 ? 'melemah' : 'menguat'} {pct(Math.abs(p.chg1m), 1).replace('+', '')}</span>
          </li>
        ))}
      </ul>
      <h3 className="hero-sub" style={{marginTop: 'var(--s4)'}}>Yang mendorong USD/IDR · 1 bln</h3>
      <ul className="drivers">
        {k.drivers.map(d => {
          const p = PUSH[d.push];
          return (
            <li key={d.key}>
              <span className="drv-main">
                <b>{d.label}</b>
                <span className="caption">{d.why}</span>
              </span>
              <span className="drv-side">
                <span className="num">{d.unit === 'idr' ? `${d.value < 0 ? 'Jual' : 'Beli'} ${compact(Math.abs(d.value))}` : d.unit === 'pp' ? `${d.value > 0 ? '+' : d.value < 0 ? '\u2212' : ''}${num(Math.abs(d.value), 1)} poin %` : pct(d.value, 1)}</span>
                <span className={`${p.cls} factor-side`}><Mark icon={p.icon} />{p.text}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </>
  );
}

export function KursFocus({onAuth, pick}: {onAuth: () => void; pick?: string}) {
  const {num, pct} = useT();
  const k = useLoad(api.kurs, [], onAuth);
  const [which, setWhich] = useState<'usd' | 'cny'>(pick === 'CNYIDR' ? 'cny' : 'usd');
  if (!k.data) return <div className="card"><Skeleton lines={6} /></div>;
  const r = k.data[which];
  if (!r) return <div className="card"><p className="body" style={{margin: 0}}>Belum ada data kurs.</p></div>;
  const cur = which === 'usd' ? 'USD' : 'CNY';
  const f1 = r.forecast['1w'], f2 = r.forecast['1m'];
  return (
    <>
      <section className="card kurs-hero" aria-label="Kurs hari ini">
        <Seg label="Mata uang" value={which} onChange={v => setWhich(v as 'usd' | 'cny')}
          options={[{key: 'usd', text: 'Dolar AS'}, {key: 'cny', text: 'Yuan China'}]} />
        <div className="kurs-top">
          <div>
            <span className="caption">1 {cur} sama dengan</span>
            <b className="kurs-val">{rp(r.price, r.price < 100 ? 2 : 0)}</b>
            <SourceLine src={r.src} />
          </div>
          <Sparkline values={r.spark} label={`${cur}/IDR 3 bulan terakhir`} height={56} />
        </div>
        <div className="kurs-chg">
          {PERIODS.map(([p, lbl]) => (
            <span key={p}><ChangeText value={r.chg[p]} upIsGood={false} /> <span className="caption">{lbl}</span></span>
          ))}
        </div>
        <p className="caption" style={{margin: 0}}>Angka {cur}/IDR naik berarti rupiah melemah: Anda perlu lebih banyak rupiah untuk 1 {cur}.</p>
        <Converter key={which} rate={r.price} cur={cur} />
      </section>

      <section className="card" aria-labelledby="wajar-h">
        <div className="card-head wajar-head">
          <h2 id="wajar-h" className="h3" style={{margin: 0}}>{(r.chg['1m'] ?? 0) >= 0 ? 'Kenaikan' : 'Penurunan'} sebulan ini wajar?</h2>
          {r.normal && <span className={`tag tag-lg tag-${NORMAL_TONE[r.normal.key]}`}>{r.normal.label}</span>}
        </div>
        <p className="body">{r.sentence}</p>
        {r.normal && r.chg['1m'] != null && <NormalBar chg={r.chg['1m']} sd={r.normal.sd} />}
        <h3 className="hero-sub" style={{marginTop: 'var(--s4)'}}>Posisi dalam setahun</h3>
        <YearBar r={r} />
        {which === 'cny' && k.data.cny?.parts && (
          <p className="body" style={{marginBottom: 0}}>
            <b>Kenapa yuan bergerak terhadap rupiah:</b> 1 yuan = rupiah per dolar ÷ yuan per dolar. {k.data.cny.parts.text}
          </p>
        )}
      </section>

      {which === 'usd' && k.data.drivers.length > 0 && <section className="card" aria-label="Penyebab"><Drivers k={k.data} /></section>}

      {(f1 || f2) && (
        <section className="card" aria-labelledby="kf-h">
          <h2 id="kf-h" className="h3" style={{marginTop: 0}}>Prakiraan model ARAH</h2>
          <div className="kurs-fc">
            {[['1 mgg lagi', f1], ['1 bln lagi', f2]].map(([lbl, f]) => f && typeof f !== 'string' && (
              <div key={lbl as string}>
                <span className="caption">{lbl as string}</span>
                <b>{num(f.q05, 0)} – {num(f.q95, 0)}</b>
                <span className="caption">9 dari 10 kemungkinan · tengah {num(f.q50, 0)} · peluang naik {pct(f.p_up * 100, 0).replace('+', '')}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {k.data.news.length > 0 && (
        <section className="card" aria-labelledby="kn-h">
          <h2 id="kn-h" className="h3" style={{marginTop: 0}}>Berita kurs</h2>
          <ul className="kurs-news">
            {k.data.news.map(n => (
              <li key={n.url}>
                <a href={n.url} target="_blank" rel="noopener noreferrer">{n.title}</a>
                <span className="caption">{n.sources.slice(0, 3).join(', ')}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
