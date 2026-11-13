/* Building blocks from the redesign pack (SPEC.md, "Design tokens" and prompt 01). Every colour comes from
   tokens.css; every icon is a 1.75px-stroke SVG on a 24px grid, hidden from screen readers, inside a named
   control. */
import {useEffect, useRef, useState, type ReactNode} from 'react';
import {api, type TagInfo} from './api';
import {useT} from './i18n';

/* ---------- Icons ---------- */

const PATHS: Record<string, ReactNode> = {
  home: <path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z" />,
  market: <><path d="M5 20V12" /><path d="M10 20V6" /><path d="M15 20v-9" /><path d="M20 20V9" /><path d="M3 20h18" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
  bell: <><path d="M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z" /><path d="M10 20a2 2 0 0 0 4 0" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /></>,
  star: <path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.8z" />,
  back: <path d="M15 5l-7 7 7 7" />,
  chevron: <path d="M6 9l6 6 6-6" />,
  next: <path d="M9 5l7 7-7 7" />,
  close: <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>,
  chat: <path d="M4 5h16v11H9l-5 4z" />,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  news: <><path d="M4 5h13v14H6a2 2 0 0 1-2-2z" /><path d="M17 9h3v8a2 2 0 0 1-2 2" /><path d="M8 9h5M8 13h5" /></>,
  check: <path d="M5 12l5 5 9-10" />,
};

export function Icon({name, size = 20, className}: {name: keyof typeof PATHS | string; size?: number; className?: string}) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{PATHS[name]}</svg>
  );
}

/** The four action marks and the three direction marks, drawn so meaning never rests on colour alone. */
function Mark({icon}: {icon: string}) {
  const common = {width: 10, height: 10, viewBox: '0 0 10 10', 'aria-hidden': true as const, className: 'mark'};
  if (icon === 'full') return <svg {...common}><circle cx="5" cy="5" r="4.5" fill="currentColor" /></svg>;
  if (icon === 'half') return <svg {...common}><circle cx="5" cy="5" r="4" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M5 1a4 4 0 0 0 0 8z" fill="currentColor" /></svg>;
  if (icon === 'square') return <svg {...common}><rect x="1" y="1" width="8" height="8" fill="currentColor" /></svg>;
  if (icon === 'up') return <svg {...common}><path d="M5 1l4.5 8h-9z" fill="currentColor" /></svg>;
  return <svg {...common}><path d="M5 9L.5 1h9z" fill="currentColor" /></svg>;
}

/* ---------- Tags ---------- */

export function Tag({tone, icon, children, size = 'sm'}: {tone: 'green' | 'grey' | 'orange'; icon?: string; children: ReactNode; size?: 'sm' | 'lg'}) {
  return <span className={`tag tag-${tone} tag-${size}`}>{icon && <Mark icon={icon} />}{children}</span>;
}

/** Masuk / Masuk bertahap / Tunggu / Hindari for stocks, Naik / Datar / Turun for markets. */
export function VerdictTag({tag, prefix, suffix, paused}: {tag: TagInfo | null | undefined; prefix?: string; suffix?: string; paused?: boolean}) {
  if (!tag) return <span className="tag tag-grey tag-sm">Belum ada data</span>;
  if (paused) return <Tag tone="grey" icon="square">Sinyal dijeda</Tag>;
  return <Tag tone={tag.tone} icon={tag.icon}>{prefix}{prefix ? tag.label.toLowerCase() : tag.label}{suffix}</Tag>;
}

/* ---------- Numbers ---------- */

/** ▲/▼ follows the price; the colour follows what it means for a rupiah holder (a rising USD/IDR is bad). */
export function ChangeText({value, upIsGood = true, label, digits = 1}: {value: number | null | undefined; upIsGood?: boolean; label?: string; digits?: number}) {
  const {pct} = useT();
  if (value == null) return <span className="muted">Tidak ada data</span>;
  const flat = Math.abs(value) < 0.5 * 10 ** -digits;
  const good = value >= 0 ? upIsGood : !upIsGood;
  return (
    <span className={`chg ${flat ? 'chg-flat' : good ? 'chg-up' : 'chg-down'}`}>
      {!flat && <Mark icon={value >= 0 ? 'up' : 'down'} />}{pct(value, digits)}{label ? ` ${label}` : ''}
    </span>
  );
}

/* ---------- Controls ---------- */

export function Seg({label, value, options, onChange, small}: {label: string; value: string; options: {key: string; text: string}[]; onChange: (k: string) => void; small?: boolean}) {
  return (
    <div className={`seg${small ? ' seg-sm' : ''}`} role="group" aria-label={label}>
      {options.map(o => (
        <button key={o.key} type="button" aria-pressed={value === o.key} onClick={() => onChange(o.key)}>{o.text}</button>
      ))}
    </div>
  );
}

/** Bottom sheet on a phone, centred dialog on a wide screen. Focus stays inside; Esc and the backdrop close it. */
export function Sheet({title, onClose, children}: {title: string; onClose: () => void; children: ReactNode}) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const el = box.current;
    const focusables = () => Array.from(el?.querySelectorAll<HTMLElement>('button, a[href], input, textarea, select, [tabindex="0"]') ?? []).filter(x => !x.hasAttribute('disabled'));
    (focusables()[1] ?? focusables()[0])?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.preventDefault(); onClose(); }
      if (e.key === 'Tab') {
        const f = focusables();
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    document.body.classList.add('no-scroll');
    return () => { document.removeEventListener('keydown', onKey); document.body.classList.remove('no-scroll'); prev?.focus?.(); };
  }, [onClose]);
  return (
    <div className="sheet-wrap" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label={title} ref={box}>
        <div className="sheet-grip" aria-hidden="true" />
        <div className="sheet-head">
          <h2 className="h2">{title}</h2>
          <button type="button" className="icon-btn" aria-label="Tutup" onClick={onClose}><Icon name="close" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ---------- Toast ---------- */

type ToastMsg = {text: string; action?: {label: string; run: () => void}};
let pushToast: ((m: ToastMsg) => void) | null = null;
export const toast = (m: ToastMsg) => pushToast?.(m);

export function ToastHost() {
  const [m, setM] = useState<ToastMsg | null>(null);
  useEffect(() => {
    pushToast = x => setM(x);
    return () => { pushToast = null; };
  }, []);
  useEffect(() => {
    if (!m) return;
    const id = window.setTimeout(() => setM(null), 6000);
    return () => window.clearTimeout(id);
  }, [m]);
  if (!m) return null;
  return (
    <div className="toast" role="status">
      <span>{m.text}</span>
      {m.action && <button type="button" onClick={() => { m.action!.run(); setM(null); }}>{m.action.label}</button>}
    </div>
  );
}

/* ---------- Sparkline with a forecast cone ---------- */

export function Sparkline({values, range, label, height = 64}: {values: number[]; range?: [number, number] | null; label: string; height?: number}) {
  if (values.length < 2) return <div className="spark-empty" style={{height}} aria-hidden="true" />;
  const W = 240, H = height, pad = 4;
  const histW = range ? W * 0.79 : W;
  const all = range ? [...values, range[0], range[1]] : values;
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const x = (i: number) => (i / (values.length - 1)) * histW;
  const y = (v: number) => pad + (1 - (v - lo) / span) * (H - 2 * pad);
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const last = values[values.length - 1];
  const mid = range ? (range[0] + range[1]) / 2 : last;
  return (
    <svg className="spark" viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={label} preserveAspectRatio="none">
      {range && <path d={`M${histW} ${y(last)} L${W - 1} ${y(range[1])} L${W - 1} ${y(range[0])} Z`} className="spark-cone" vectorEffect="non-scaling-stroke" />}
      <path d={line} className="spark-line" vectorEffect="non-scaling-stroke" />
      {range && <path d={`M${histW} ${y(last)} L${W - 5} ${y(mid)}`} className="spark-mid" vectorEffect="non-scaling-stroke" />}
      {range && <circle cx={W - 5} cy={y(mid)} r="4" className="spark-dot" />}
    </svg>
  );
}

/* ---------- Where a number comes from ---------- */

export interface SrcInfo {source: string; at: number; delay_min: number}

/** "Stockbit · 14.30 · realtime" or "Yahoo · 14.15 · tertunda 15 mnt": every price says where and when. */
export function SourceLine({src, className = 'caption src-line'}: {src?: SrcInfo | null; className?: string}) {
  if (!src) return <span className={className}>Sumber: —</span>;
  const t = src.at ? new Intl.DateTimeFormat('id-ID', {hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jakarta'}).format(src.at * 1000) : '—';
  const day = src.at && Date.now() / 1000 - src.at > 18 * 3600
    ? new Intl.DateTimeFormat('id-ID', {day: 'numeric', month: 'short', timeZone: 'Asia/Jakarta'}).format(src.at * 1000) + ' ' : '';
  return <span className={className}>{src.source} · {day}{t} · {src.delay_min ? `tertunda ${src.delay_min} mnt` : 'realtime'}</span>;
}

/* ---------- Data freshness ---------- */

export interface Pulse {state: 'live' | 'delayed' | 'paused'; at: number | null; since: number | null; stockbit: boolean; delay_min: number; alerts_active: number; telegram: boolean}

const hhmm = (ts: number | null) => (ts ? new Intl.DateTimeFormat('id-ID', {hour: '2-digit', minute: '2-digit'}).format(ts * 1000) : '');

/** One component everywhere: live shows only the time; delayed is an amber chip; paused greys out signals. */
export function StaleChip({pulse, onChanged, wide}: {pulse: Pulse | null; onChanged: () => void; wide?: boolean}) {
  const [open, setOpen] = useState(false);
  if (!pulse) return null;
  if (pulse.state === 'live') return <span className="stale-live" aria-label={`Data terkini ${hhmm(pulse.at)}`}>{hhmm(pulse.at)}</span>;
  const text = pulse.state === 'paused' ? 'Sinyal dijeda' : `Tertunda ${pulse.delay_min} mnt${wide ? ' · Sambungkan' : ''}`;
  return (
    <>
      <button type="button" className="stale-chip" onClick={() => setOpen(true)}><Icon name="clock" size={14} />{text}</button>
      {open && <StockbitSheet pulse={pulse} onClose={() => setOpen(false)} onDone={() => { setOpen(false); onChanged(); }} />}
    </>
  );
}

function StockbitSheet({pulse, onClose, onDone}: {pulse: Pulse; onClose: () => void; onDone: () => void}) {
  const [show, setShow] = useState(false);
  const [val, setVal] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true); setErr(null);
    try { await api.stockbitSession(val); toast({text: 'Stockbit tersambung lagi.'}); onDone(); }
    catch { setErr('Nilai itu bukan sesi Stockbit. Salin lagi isi credentialStorage.'); }
    finally { setBusy(false); }
  };
  return (
    <Sheet title="Data tertunda" onClose={onClose}>
      <p className="body">
        {pulse.state === 'paused'
          ? 'Data belum diperbarui lebih dari sehari. Sinyal dijeda sampai data baru masuk.'
          : `${pulse.stockbit ? `Koneksi Stockbit putus${pulse.since ? ` sejak ${hhmm(pulse.since)}` : ''}.` : 'Stockbit belum tersambung.'} Harga dan sinyal memakai data terakhir.`}
      </p>
      {!show ? (
        <button type="button" className="btn btn-primary btn-block" onClick={() => setShow(true)}>Sambungkan Stockbit</button>
      ) : (
        <div className="stack">
          <ol className="steps">
            <li>Di komputer, buka stockbit.com di jendela Incognito dan login.</li>
            <li>Tekan F12, buka Application, lalu Cookies, lalu stockbit.com.</li>
            <li>Salin isi baris credentialStorage, tempel di bawah.</li>
          </ol>
          <label className="field">
            <span>Sesi Stockbit</span>
            <textarea rows={3} value={val} onChange={e => setVal(e.target.value)} placeholder="%7B%22..." />
          </label>
          {err && <p className="err" role="alert">{err}</p>}
          <button type="button" className="btn btn-primary btn-block" disabled={val.trim().length < 20 || busy} onClick={save}>
            {busy ? 'Menyambungkan…' : 'Sambungkan'}
          </button>
        </div>
      )}
    </Sheet>
  );
}

/* ---------- Loading ---------- */

export function Skeleton({lines = 3, label = 'Memuat harga…'}: {lines?: number; label?: string}) {
  return (
    <div className="skel" aria-busy="true">
      {Array.from({length: lines}).map((_, i) => <span key={i} className="skel-line" style={{width: `${92 - i * 14}%`}} />)}
      <span className="sr-only">{label}</span>
      <span className="skel-label">{label}</span>
    </div>
  );
}
