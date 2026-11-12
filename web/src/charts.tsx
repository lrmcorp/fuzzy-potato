import {useId, useRef, useState} from 'react';
import type {AssetView} from './api';
import {useT} from './i18n';

export function Spark({values, label}: {values: number[]; label: string}) {
  if (values.length < 2) return null;
  const w = 96, h = 28, min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - 2 - ((v - min) / span) * (h - 4)}`).join(' ');
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="img" aria-label={label}>
      <polyline points={pts} fill="none" stroke="var(--color-text-secondary)" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

/** History line followed by the forecast fan: 90% and 50% ranges around the midpoint. */
export function FanChart({view}: {view: AssetView}) {
  const {t, nm, num, lang} = useT();
  const titleId = useId();
  const box = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const hist = view.history ?? [];
  const band = view.forecast.band ?? [];
  if (hist.length < 2 || band.length === 0) return null;

  const W = 720, H = 300, padL = 8, padR = 64, padT = 14, padB = 28;
  const stepSec = view.meta.interval === '1h' ? 3600 : 86400;
  const lastT = hist[hist.length - 1].t;
  // Forecast steps are trading bars, so they are spaced like bars, not like calendar time.
  const points = [
    ...hist.map((p, i) => ({i, t: p.t, c: p.c, f: null as null | typeof band[0]})),
    ...band.map(b => ({i: hist.length - 1 + b.step, t: lastT + b.step * stepSec, c: b.q50, f: b})),
  ];
  const maxI = points[points.length - 1].i;
  const levels = Object.keys(view.forecast.touch).map(Number);
  const lo0 = Math.min(...hist.map(p => p.c), ...band.map(b => b.q05));
  const hi0 = Math.max(...hist.map(p => p.c), ...band.map(b => b.q95));
  const near = levels.filter(lv => lv > lo0 - (hi0 - lo0) * 0.25 && lv < hi0 + (hi0 - lo0) * 0.25);
  const lo = Math.min(lo0, ...near), hi = Math.max(hi0, ...near);
  const pad = (hi - lo) * 0.06 || 1;
  const x = (i: number) => padL + (i / maxI) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - (lo - pad)) / (hi - lo + 2 * pad)) * (H - padT - padB);
  const line = hist.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.c).toFixed(1)}`).join('');
  const startX = x(hist.length - 1), s0 = hist[hist.length - 1].c;
  const area = (a: 'q05' | 'q25', b: 'q95' | 'q75') =>
    `M${startX},${y(s0)}` + band.map(p => `L${x(hist.length - 1 + p.step).toFixed(1)},${y(p[b]).toFixed(1)}`).join('') +
    [...band].reverse().map(p => `L${x(hist.length - 1 + p.step).toFixed(1)},${y(p[a]).toFixed(1)}`).join('') + 'Z';
  const mid = `M${startX},${y(s0)}` + band.map(p => `L${x(hist.length - 1 + p.step).toFixed(1)},${y(p.q50).toFixed(1)}`).join('');
  const ticks = [lo, (lo + hi) / 2, hi];
  const fmtT = (ts: number) => new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-US',
    view.meta.interval === '1h' ? {day: 'numeric', month: 'short', hour: '2-digit'} : {day: 'numeric', month: 'short'}).format(ts * 1000);

  const onMove = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    const px = ((clientX - r.left) / r.width) * W;
    const idx = Math.round(((px - padL) / (W - padL - padR)) * maxI);
    let best = 0;
    points.forEach((p, k) => { if (Math.abs(p.i - idx) < Math.abs(points[best].i - idx)) best = k; });
    setHover(best);
  };
  const hp = hover == null ? null : points[hover];
  const d = view.decimals;

  return (
    <figure className="chart">
      <figcaption id={titleId}>{t('chart_title')}: {nm(view)}</figcaption>
      <div className="chart-wrap">
        <svg ref={box} viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby={titleId}
          onMouseMove={e => onMove(e.clientX)} onMouseLeave={() => setHover(null)}
          onTouchStart={e => onMove(e.touches[0].clientX)} onTouchMove={e => onMove(e.touches[0].clientX)}>
          {ticks.map(v => (
            <g key={v}>
              <line x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} className="grid" />
              <text x={W - padR + 6} y={y(v) + 4} className="axis">{num(v, d)}</text>
            </g>
          ))}
          {near.map(lv => (
            <g key={lv}>
              <line x1={padL} x2={W - padR} y1={y(lv)} y2={y(lv)} className="level" />
              <text x={padL + 2} y={y(lv) - 4} className="axis">{num(lv, d)}</text>
            </g>
          ))}
          <path d={area('q05', 'q95')} className="band90" />
          <path d={area('q25', 'q75')} className="band50" />
          <path d={line} className="hist" />
          <path d={mid} className="mid" />
          <line x1={startX} x2={startX} y1={padT} y2={H - padB} className="now" />
          <text x={x(0)} y={H - 8} className="axis">{fmtT(hist[0].t)}</text>
          <text x={startX} y={H - 8} className="axis" textAnchor="middle">{fmtT(lastT)}</text>
          {hp && (
            <g>
              <line x1={x(hp.i)} x2={x(hp.i)} y1={padT} y2={H - padB} className="cross" />
              <circle cx={x(hp.i)} cy={y(hp.c)} r="4" className="dot" />
            </g>
          )}
        </svg>
        {hp && (
          <div className="tip" style={{left: `${Math.min(Math.max((x(hp.i) / W) * 100, 16), 78)}%`}} role="status">
            <strong>{fmtT(hp.t)}</strong>
            {hp.f ? (
              <>
                <span>{t('chart_mid')}: {num(hp.f.q50, d)}</span>
                <span>{t('chart_50')}: {num(hp.f.q25, d)} - {num(hp.f.q75, d)}</span>
                <span>{t('chart_90')}: {num(hp.f.q05, d)} - {num(hp.f.q95, d)}</span>
              </>
            ) : <span>{t('chart_hist')}: {num(hp.c, d)}</span>}
          </div>
        )}
      </div>
      <ul className="legend">
        <li><i className="k-hist" />{t('chart_hist')}</li>
        <li><i className="k-mid" />{t('chart_mid')}</li>
        <li><i className="k-50" />{t('chart_50')}</li>
        <li><i className="k-90" />{t('chart_90')}</li>
      </ul>
      <details className="chart-table">
        <summary>{t('show_table')}</summary>
        <div className="scroll-x">
          <table>
            <thead><tr><th>{t('step')}</th><th>5%</th><th>25%</th><th>50%</th><th>75%</th><th>95%</th></tr></thead>
            <tbody>
              {band.map(b => (
                <tr key={b.step}><td>{b.step}</td><td>{num(b.q05, d)}</td><td>{num(b.q25, d)}</td><td>{num(b.q50, d)}</td>
                  <td>{num(b.q75, d)}</td><td>{num(b.q95, d)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
