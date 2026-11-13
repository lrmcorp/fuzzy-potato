import {useEffect, useId, useRef, useState} from 'react';
import {AreaSeries, CandlestickSeries, ColorType, CrosshairMode, createChart, type IChartApi, type ISeriesApi, type UTCTimestamp} from 'lightweight-charts';
import type {AssetView, Bar, Forecast, Technique} from './api';
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

/** Card chart: the last ~3 months of daily closes, then a cone out to next month's reasonable range.
 *  The cone is tinted by whether next month looks good or not for the owner. */
export function MiniFan({values, range, state, label}: {values: number[]; range?: [number, number]; state?: 'good' | 'neutral' | 'bad'; label: string}) {
  if (values.length < 2) return <div className="mini mini-empty" aria-hidden="true" />;
  const W = 320, H = 96, pad = 4;
  const histW = range ? W * 0.74 : W;
  const all = range ? [...values, range[0], range[1]] : values;
  const lo = Math.min(...all), hi = Math.max(...all), span = hi - lo || 1;
  const x = (i: number) => (i / (values.length - 1)) * histW;
  const y = (v: number) => pad + (1 - (v - lo) / span) * (H - 2 * pad);
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('');
  const area = `${line}L${histW},${H}L0,${H}Z`;
  const last = values[values.length - 1];
  const cone = range && `M${histW},${y(last)}L${W - 2},${y(range[1])}L${W - 2},${y(range[0])}Z`;
  const mid = range && `M${histW},${y(last)}L${W - 2},${y((range[0] + range[1]) / 2)}`;
  return (
    <svg className="mini" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={label}>
      <path d={area} className="mini-area" />
      <path d={line} className="mini-line" vectorEffect="non-scaling-stroke" />
      {cone && <path d={cone} className={`mini-cone mini-${state ?? 'flat'}`} />}
      {mid && <path d={mid} className={`mini-mid mini-${state ?? 'flat'}-s`} vectorEffect="non-scaling-stroke" />}
      {range && <line x1={histW} x2={histW} y1={0} y2={H} className="mini-now" vectorEffect="non-scaling-stroke" />}
    </svg>
  );
}

/** Today's minute bars, Stockbit-style. Candles are ink only: hollow when the minute rose, filled when it fell,
 *  because colour on this site means good or bad for the owner, not up or down. */
export function LiveChart({bars, decimals, label}: {bars: Bar[]; decimals: number; label: string}) {
  const box = useRef<HTMLDivElement>(null);
  const chart = useRef<IChartApi | null>(null);
  const series = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Area'> | null>(null);
  const flat = bars.length > 0 && bars.every(b => b.o === b.c && b.h === b.c && b.l === b.c);
  const kind = flat ? 'area' : 'candle';
  // Daily closes (the fallback when minute prices are refused) are labelled by date, not by time.
  const daily = bars.length > 1 && bars[1].t - bars[0].t >= 86400;

  useEffect(() => {
    if (!box.current) return;
    const css = getComputedStyle(document.documentElement);
    const ink = css.getPropertyValue('--color-text-primary').trim() || '#0a1317';
    const muted = css.getPropertyValue('--color-text-secondary').trim() || '#4e606f';
    const grid = css.getPropertyValue('--color-border').trim() || '#e5e9ee';
    const fmtTime = (ts: number) => new Intl.DateTimeFormat(undefined, daily ? {day: 'numeric', month: 'short'} : {hour: '2-digit', minute: '2-digit'}).format(ts * 1000);
    const c = createChart(box.current, {
      autoSize: true,
      layout: {background: {type: ColorType.Solid, color: 'transparent'}, textColor: muted, fontSize: 11, attributionLogo: false},
      grid: {vertLines: {visible: false}, horzLines: {color: grid}},
      rightPriceScale: {borderVisible: false},
      timeScale: {borderVisible: false, timeVisible: true, secondsVisible: false, tickMarkFormatter: (ts: number) => fmtTime(ts)},
      localization: {timeFormatter: (ts: number) => fmtTime(ts), priceFormatter: (p: number) => p.toLocaleString('en-US', {minimumFractionDigits: decimals, maximumFractionDigits: decimals})},
      crosshair: {mode: CrosshairMode.Magnet},
      handleScroll: {vertTouchDrag: false},
    });
    series.current = kind === 'candle'
      ? c.addSeries(CandlestickSeries, {upColor: 'rgba(0,0,0,0)', downColor: ink, borderUpColor: ink, borderDownColor: ink,
          wickUpColor: ink, wickDownColor: ink, priceLineColor: ink})
      : c.addSeries(AreaSeries, {lineColor: ink, lineWidth: 2, topColor: 'rgba(15,107,99,0.18)', bottomColor: 'rgba(15,107,99,0.02)', priceLineColor: ink});
    chart.current = c;
    return () => { c.remove(); chart.current = null; series.current = null; };
  }, [kind, decimals, daily]);

  useEffect(() => {
    const s = series.current;
    if (!s) return;
    const seen = new Set<number>();
    const rows = bars.filter(b => !seen.has(b.t) && seen.add(b.t));
    if (kind === 'candle') {
      (s as ISeriesApi<'Candlestick'>).setData(rows.map(b => ({time: b.t as UTCTimestamp, open: b.o, high: b.h, low: b.l, close: b.c})));
    } else {
      (s as ISeriesApi<'Area'>).setData(rows.map(b => ({time: b.t as UTCTimestamp, value: b.c})));
    }
  }, [bars, kind]);

  return <div className="live-chart" ref={box} role="img" aria-label={label} />;
}

const LINE_KEYS = ['trend', 'season', 'analog'] as const;

/** Six months of daily closes, then the combined forecast as a fan (50% and 90% ranges) and the path each
 *  technique implies. Lines carry their own labels at the right edge so colour is never the only cue. */
export function ProjectionChart({f}: {f: Forecast}) {
  const {t, l, num, lang} = useT();
  const titleId = useId();
  const box = useRef<SVGSVGElement>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [width, setWidth] = useState(720);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const hist = f.history;
  const band = f.conclusion.band;
  if (hist.length < 2 || band.length === 0) return null;
  const lines = LINE_KEYS.map(k => f.techniques.find(x => x.key === k)).filter((x): x is Technique => !!x && !!x.path && x.path.length > 1);

  // Drawn at the container's real width so text stays readable on a phone.
  const narrow = width < 520;
  const W = width, H = narrow ? 280 : 340, padL = 4, padR = narrow ? 84 : 128, padT = 16, padB = 26;
  const n0 = hist.length - 1;
  const maxI = n0 + f.steps;
  const pathAt = (p: number[], step: number) => p[Math.min(p.length - 1, Math.round(step * (p.length - 1) / f.steps))];
  const values = [...hist.map(p => p.c), ...band.flatMap(b => [b.q05, b.q95]), ...lines.flatMap(x => x.path ?? [])];
  const lo0 = Math.min(...values), hi0 = Math.max(...values), pad = (hi0 - lo0) * 0.06 || 1;
  const lo = lo0 - pad, hi = hi0 + pad;
  const x = (i: number) => padL + (i / maxI) * (W - padL - padR);
  const y = (v: number) => padT + (1 - (v - lo) / (hi - lo)) * (H - padT - padB);
  const d = f.decimals;
  const s0 = f.s0;
  const histPath = hist.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.c).toFixed(1)}`).join('');
  const area = (a: 'q05' | 'q25', b: 'q95' | 'q75') =>
    `M${x(n0)},${y(s0)}` + band.map(p => `L${x(n0 + p.step).toFixed(1)},${y(p[b]).toFixed(1)}`).join('') +
    [...band].reverse().map(p => `L${x(n0 + p.step).toFixed(1)},${y(p[a]).toFixed(1)}`).join('') + 'Z';
  const mid = `M${x(n0)},${y(s0)}` + band.map(p => `L${x(n0 + p.step).toFixed(1)},${y(p.q50).toFixed(1)}`).join('');
  const techLine = (p: number[]) => p.map((v, i) => `${i ? 'L' : 'M'}${x(n0 + (i * f.steps) / (p.length - 1)).toFixed(1)},${y(v).toFixed(1)}`).join('');
  // End labels, nudged apart so they never overlap.
  const ends = [
    {key: 'mid', label: t('conclusion'), v: band[band.length - 1].q50},
    ...lines.map(x2 => ({key: x2.key, label: narrow ? t(`short_${x2.key}` as 'short_trend') : l(x2.name), v: (x2.path as number[])[(x2.path as number[]).length - 1]})),
  ].map(e => ({...e, yy: y(e.v)})).sort((a, b) => a.yy - b.yy);
  for (let i = 1; i < ends.length; i++) if (ends[i].yy - ends[i - 1].yy < 14) ends[i].yy = ends[i - 1].yy + 14;
  const dateFmt = new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-US', {day: 'numeric', month: 'short'});
  const ticks = [lo0, (lo0 + hi0) / 2, hi0];

  const onMove = (clientX: number) => {
    const r = box.current?.getBoundingClientRect();
    if (!r) return;
    const i = Math.round((((clientX - r.left) / r.width) * W - padL) / (W - padL - padR) * maxI);
    setHover(Math.max(0, Math.min(maxI, i)));
  };
  const hb = hover != null && hover > n0 ? band.reduce((a, b) => (Math.abs(n0 + b.step - hover) < Math.abs(n0 + a.step - hover) ? b : a)) : null;

  return (
    <figure className="chart proj">
      <figcaption id={titleId}>{t('proj_title')}: {f.horizon_name[lang]}</figcaption>
      <div className="chart-wrap" ref={wrap}>
        <svg ref={box} viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="proj-svg" role="img" aria-labelledby={titleId}
          onMouseMove={e => onMove(e.clientX)} onMouseLeave={() => setHover(null)}
          onTouchStart={e => onMove(e.touches[0].clientX)} onTouchMove={e => onMove(e.touches[0].clientX)}>
          {ticks.map(v => (
            <g key={v}><line x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} className="grid" />
              <text x={padL + 2} y={y(v) - 4} className="axis">{num(v, d)}</text></g>
          ))}
          <path d={area('q05', 'q95')} className="band90" />
          <path d={area('q25', 'q75')} className="band50" />
          <path d={histPath} className="hist" />
          {lines.map(x2 => <path key={x2.key} d={techLine(x2.path as number[])} className={`tech tech-${x2.key}`} />)}
          <path d={mid} className="mid" />
          <line x1={x(n0)} x2={x(n0)} y1={padT} y2={H - padB} className="now" />
          <text x={x(0)} y={H - 8} className="axis">{dateFmt.format(hist[0].t * 1000)}</text>
          <text x={x(n0)} y={H - 8} className="axis" textAnchor="middle">{t('today')}</text>
          <text x={W - padR} y={H - 8} className="axis" textAnchor="end">+{f.horizon_name[lang]}</text>
          {ends.map(e => (
            <g key={e.key}>
              <circle cx={W - padR} cy={y(e.v)} r="3" className={e.key === 'mid' ? 'end-mid' : `end-dot tech-${e.key}`} />
              <text x={W - padR + 8} y={e.yy + 4} className={`end-label ${e.key === 'mid' ? 'end-strong' : ''}`}>{e.label}</text>
            </g>
          ))}
          {hover != null && <line x1={x(hover)} x2={x(hover)} y1={padT} y2={H - padB} className="cross" />}
        </svg>
        {hover != null && (
          <div className="tip" style={{left: `${Math.min(Math.max((x(hover) / W) * 100, 18), 72)}%`}} role="status">
            {hover <= n0 ? (
              <><strong>{dateFmt.format(hist[hover].t * 1000)}</strong><span>{num(hist[hover].c, d)}</span></>
            ) : hb && (
              <>
                <strong>{t('day_n', {n: hb.step})}</strong>
                <span>{t('conclusion')}: {num(hb.q50, d)}</span>
                <span>{t('chart_90')}: {num(hb.q05, d)} – {num(hb.q95, d)}</span>
                {lines.map(x2 => <span key={x2.key}>{l(x2.name)}: {num(pathAt(x2.path as number[], hb.step), d)}</span>)}
              </>
            )}
          </div>
        )}
      </div>
      <ul className="legend">
        <li><i className="k-hist" />{t('chart_hist')}</li>
        <li><i className="k-mid" />{t('conclusion')}</li>
        <li><i className="k-50" />{t('chart_50')}</li>
        <li><i className="k-90" />{t('chart_90')}</li>
        {lines.map(x2 => <li key={x2.key}><i className={`k-tech tech-${x2.key}`} />{l(x2.name)}</li>)}
      </ul>
      <details className="chart-table">
        <summary>{t('show_table')}</summary>
        <div className="scroll-x">
          <table>
            <thead><tr><th>{t('step')}</th><th>5%</th><th>50%</th><th>95%</th>{lines.map(x2 => <th key={x2.key}>{l(x2.name)}</th>)}</tr></thead>
            <tbody>{band.map(b => (
              <tr key={b.step}><td>{b.step}</td><td>{num(b.q05, d)}</td><td>{num(b.q50, d)}</td><td>{num(b.q95, d)}</td>
                {lines.map(x2 => <td key={x2.key}>{num(pathAt(x2.path as number[], b.step), d)}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      </details>
    </figure>
  );
}
