import {useEffect, useRef, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Banner} from '@astryxdesign/core/Banner';
import {Button} from '@astryxdesign/core/Button';
import {Card} from '@astryxdesign/core/Card';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {Heading} from '@astryxdesign/core/Heading';
import {SegmentedControl, SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import {Selector} from '@astryxdesign/core/Selector';
import {Spinner} from '@astryxdesign/core/Spinner';
import {TextInput} from '@astryxdesign/core/TextInput';
import {api, ApiError, type Answer, type Brief, type Calc, type EventItem, type Forecast, type Technique, type Lang, type MarketRow, type RecCard, type Simple, type SimpleCard, type State} from './api';
import {FanChart, LiveChart, MiniFan, ProjectionChart, Spark} from './charts';
import {AssetLink, Async, Glyph, GradeNote, HorizonStrip, Lines, Reasons, Verdict, VigilanceLine} from './components';
import {useLoad} from './hooks';
import {useT} from './i18n';

interface PageProps {onAuth: () => void}
const HORIZONS = ['1h', '4h', '1d', '1w', '2w', '3w', '1m'];

function Chip({label, state, name}: {label: string; state: State; name: string}) {
  return <span className={`chip chip-${state}`}><span className="chip-k">{label}</span> {name}</span>;
}

/** A rising rupiah rate means a weaker rupiah, so for currencies up is shown as bad. */
const good = (chg: number | null | undefined, klass: string) => ((chg ?? 0) >= 0) !== (klass === 'fx');

/** One card per question: price, two answers, a chart, one line of numbers. Everything else is on the detail page. */
function Tile({title, card, h}: {title: string; card: SimpleCard; h: H3}) {
  const {t, l, money, pct} = useT();
  const d = card.decimals;
  const u = card.unit;
  const [lo, hi] = card.next.range;
  return (
    <a className="tile" href={`#/a/${card.key}`}>
      <div className="tile-top">
        <span className="tile-name">{title}</span>
        {card.chg1d != null && <span className={`delta ${good(card.chg1d, card.klass) ? 'delta-up' : 'delta-down'}`}>{pct(card.chg1d)} <span className="muted">{t('today')}</span></span>}
      </div>
      <div className="tile-price">{money(card.price, card.price < 1000 ? 2 : d, u)}</div>
      <div className="chips">
        <Chip label={t('now')} state={card.now.state} name={l(card.now.name)} />
        <Chip label={t(`in_${h}`)} state={card.next.state} name={l(card.next.name)} />
      </div>
      <MiniFan values={card.spark ?? []} range={card.spark?.length ? card.next.range : undefined} state={card.next.state}
        label={`${title}: ${t('chart_title')}`} />
      <div className="tile-foot">
        <span>{t(`range_${h}`)}</span>
        <strong>{money(lo, lo < 1000 ? 2 : d, u)} – {money(hi, hi < 1000 ? 2 : d, u)}</strong>
      </div>
    </a>
  );
}

function AbroadTile({ab, h}: {ab: NonNullable<Simple['abroad']>; h: H3}) {
  const {t, l, pct} = useT();
  return (
    <div className="tile">
      <div className="tile-top"><span className="tile-name">{t('q_abroad')}</span></div>
      <div className="chips">
        <Chip label={t('now')} state={ab.now.state} name={l(ab.now.name)} />
        <Chip label={t(`in_${h}`)} state={ab.next.state} name={l(ab.next.name)} />
      </div>
      <ul className="rows">
        {ab.countries.map(c => (
          <li key={c.key}>
            <a href={`#/a/${c.key}`}>
              <span className="row-name">{t(`c_${c.country}` as 'c_US')}</span>
              <Spark values={c.spark ?? []} label={t(`c_${c.country}` as 'c_US')} />
              <span className={`delta ${good(c.chg1m, c.klass) ? 'delta-up' : 'delta-down'}`}>{pct(c.chg1m)}</span>
            </a>
          </li>
        ))}
      </ul>
      <div className="tile-foot"><span>{t('abroad_foot')}</span><span>{t('month')}</span></div>
    </div>
  );
}

export function Today({onAuth}: PageProps) {
  const {t} = useT();
  const state = useLoad(api.brief, [], onAuth);
  const [busy, setBusy] = useState(false);
  const building = busy || !!state.data?.building;
  const ready = !!state.data?.brief?.simple;
  useEffect(() => {
    if (!building && ready) return;
    const id = window.setInterval(state.reload, 5000);
    return () => window.clearInterval(id);
  }, [building, ready, state.reload]);
  useEffect(() => { if (state.data && !state.data.building) setBusy(false); }, [state.data]);

  const rebuild = async () => { setBusy(true); try { await api.runBrief(); } finally { state.reload(); } };

  return (
    <Async state={state}>
      {({brief, llm_error, llm_enabled}) => !brief || !brief.simple ? (
        <EmptyState title={t('no_brief_title')} description={t('no_brief_desc')} actions={<Spinner size="md" />} />
      ) : (
        <>
          {llm_error && <Banner status="warning" title={t(`llm_${llm_error}` as const)} />}
          <Summary brief={brief} simple={brief.simple} building={building} rebuild={rebuild} canAsk={llm_enabled} />
        </>
      )}
    </Async>
  );
}

type H3 = '1m' | '2m' | '3m';

function HorizonTabs({value, onChange}: {value: H3; onChange: (h: H3) => void}) {
  const {t} = useT();
  return (
    <SegmentedControl label={t('horizon')} value={value} onChange={v => onChange(v as H3)}>
      <SegmentedControlItem value="1m" label={t('h_1m')} />
      <SegmentedControlItem value="2m" label={t('h_2m')} />
      <SegmentedControlItem value="3m" label={t('h_3m')} />
    </SegmentedControl>
  );
}

function Summary({brief, simple: first, building, rebuild, canAsk}: {brief: Brief; simple: Simple; building: boolean; rebuild: () => void; canAsk: boolean}) {
  const {t, l, when, lang} = useT();
  const [h, setH] = useState<H3>('1m');
  const other = useLoad(() => (h === '1m' ? Promise.resolve(first) : api.simple(h)), [h, first]);
  const simple = h === '1m' ? first : other.data;
  const dayOf = (ts: number) => new Intl.DateTimeFormat(lang === 'id' ? 'id-ID' : 'en-US', {weekday: 'short', day: 'numeric', month: 'short'}).format(ts * 1000);
  return (
    <>
      <header className="dash-head">
        <div>
          <p className="kicker">{t('updated')} {when(brief.at)}</p>
          <h1 className="headline">{l(brief.headline)}</h1>
        </div>
        <Button label={building ? t('building') : t('refresh')} size="sm" onClick={rebuild} isLoading={building} />
      </header>
      {brief.outlook && (
        <details className="why why-top">
          <summary>{t('my_view')}</summary>
          <p>{l(brief.outlook)}</p>
        </details>
      )}
      <div className="filter-row">
        <span className="filter-label">{t('forecast_for')}</span>
        <HorizonTabs value={h} onChange={setH} />
      </div>
      {!simple ? <Lines n={6} /> : (
        <div className={`tiles${other.loading && h !== '1m' ? ' is-loading' : ''}`}>
          {simple.indonesia && <Tile title={t('q_id_short')} card={simple.indonesia} h={h} />}
          {simple.abroad && <AbroadTile ab={simple.abroad} h={h} />}
          {simple.usd && <Tile title="USD / IDR" card={simple.usd} h={h} />}
          {simple.cny && <Tile title="CNY / IDR" card={simple.cny} h={h} />}
        </div>
      )}
      <p className="legend-line">
        <span className="chip chip-good">{t('good')}</span> {t('legend_good')}
        <span className="chip chip-neutral">{t('neutral')}</span> {t('legend_neutral')}
        <span className="chip chip-bad">{t('bad')}</span> {t('legend_bad')}
      </p>

      <Events items={brief.events ?? []} dayOf={dayOf} />

      {canAsk && <AskBox />}
    </>
  );
}

/** Coming events, Indonesia or the world in one tap; the five soonest first, up to ten on request. */
function Events({items, dayOf}: {items: EventItem[]; dayOf: (ts: number) => string}) {
  const {t, l} = useT();
  const [side, setSide] = useState<'world' | 'id'>('world');
  const [all, setAll] = useState(false);
  // Briefs made before the split carry no side: Indonesia is its own side, every other country is the world.
  const list = items.filter(e => (e.side ?? (e.country === 'ID' ? 'id' : 'world')) === side).slice(0, 10);
  const shown = all ? list : list.slice(0, 5);
  return (
    <section className="block" aria-labelledby="q-ev">
      <div className="block-top">
        <h2 id="q-ev" className="block-h">{t('events_h')}</h2>
        <SegmentedControl label={t('ev_side')} value={side} onChange={v => { setSide(v as 'world' | 'id'); setAll(false); }}>
          <SegmentedControlItem value="world" label={t('ev_world')} />
          <SegmentedControlItem value="id" label={t('ev_id')} />
        </SegmentedControl>
      </div>
      {shown.length === 0 ? <p className="note">{t(side === 'id' ? 'no_events_id' : 'no_events')}</p> : (
        <ul className="events">
          {shown.map((e, i) => (
            <li key={i}>
              <span className="event-when">{dayOf(e.at)}<br /><span className="muted">{t(`c_${e.country}` as 'c_US')}</span></span>
              <span>{e.title ?? l(e.what)}{e.source === 'news' && <span className="muted small"> · {t('from_news')}</span>}</span>
            </li>
          ))}
        </ul>
      )}
      {list.length > 5 && (
        <Button label={all ? t('ev_less') : t('ev_more', {n: list.length})} size="sm" variant="ghost" onClick={() => setAll(!all)} />
      )}
    </section>
  );
}

function AskBox() {
  const {t, l} = useT();
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [a, setA] = useState<Answer | null>(null);
  const send = async () => {
    if (q.trim().length < 5) { setErr(t('ask_short')); return; }
    setBusy(true); setErr(null); setA(null);
    try { setA(await api.ask(q.trim())); } catch { setErr(t('ask_fail')); } finally { setBusy(false); }
  };
  return (
    <section className="block" aria-labelledby="q-ask">
      <h2 id="q-ask" className="block-h">{t('ask_h')}</h2>
      <div className="toolbar">
        <TextInput label={t('ask_label')} placeholder={t('ask_ph')} value={q} onChange={setQ} onEnter={send} width="100%"
          status={err ? {type: 'error', message: err} : undefined} />
        <Button label={t('ask_btn')} variant="primary" onClick={send} isLoading={busy} />
      </div>
      {a && (
        <div aria-live="polite">
          <div className="chips"><Chip label={`${t('conf')} ${t(`c_${a.confidence}` as const)}`} state={a.verdict} name={t(a.verdict)} /></div>
          <p className="verdict">{l(a.answer)}</p>
          <Reasons items={a.points} />
          {a.risk && <p className="watch"><strong>{t('risk_one')}:</strong> {l(a.risk)}</p>}
        </div>
      )}
    </section>
  );
}

export function CalcPage({onAuth}: PageProps) {
  const {t, l, num, money, when, lang} = useT();
  const [amount, setAmount] = useState('100000000');
  const [cur, setCur] = useState('USD');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [c, setC] = useState<Calc | null>(null);
  const run = async () => {
    const v = Number(amount.replace(/[^0-9]/g, ''));
    if (!(v > 0)) { setErr(t('calc_bad')); return; }
    setBusy(true); setErr(null);
    try { setC(await api.calc(v, cur)); }
    catch (e) { if (e instanceof ApiError && e.status === 401) onAuth(); setErr(t('load_failed')); }
    finally { setBusy(false); }
  };
  const names: Record<string, [string, string]> = {USD: ['Dolar AS (USD)', 'US dollar (USD)'], CNY: ['Yuan China (RMB)', 'Chinese yuan (RMB)'],
    SGD: ['Dolar Singapura (SGD)', 'Singapore dollar (SGD)'], JPY: ['Yen Jepang (JPY)', 'Japanese yen (JPY)'], EUR: ['Euro (EUR)', 'Euro (EUR)']};
  return (
    <>
      <header className="page-head"><Heading level={1}>{t('calc_title')}</Heading><p className="lead">{t('calc_lead')}</p></header>
      <div className="toolbar">
        <TextInput label={t('amount')} value={amount} onChange={setAmount} onEnter={run} inputMode="numeric" width={200}
          status={err ? {type: 'error', message: err} : undefined} />
        <Selector label={t('currency')} value={cur} onChange={setCur} width={220}
          options={Object.entries(names).map(([k, v]) => ({value: k, label: v[lang === 'id' ? 0 : 1]}))} />
        <Button label={t('calc_btn')} variant="primary" onClick={run} isLoading={busy} />
      </div>
      {c && (
        <section className="answer" aria-live="polite">
          <p className="verdict">{l(c.summary)}</p>
          <p className="answer-line">{t('rate')}: {money(c.rate, 2, 'Rp')} ({t(c.source === 'bca' ? 'rate_bca' : 'rate_market')}{c.rate_at ? `, ${when(c.rate_at)}` : ''})</p>
          <p className="answer-line">{t('in_month')} {num(c.next_low, 2)} {t('to')} {num(c.next_high, 2)} {c.currency}.</p>
          <p className="answer-line"><strong>{l(c.advice)}</strong></p>
        </section>
      )}
    </>
  );
}

function MarketTable({rows}: {rows: MarketRow[]}) {
  const {t, nm, num, money, pct} = useT();
  return (
    <div className="scroll-x">
      <table className="market">
        <thead><tr><th>{t('name')}</th><th>{t('price')}</th><th>{t('today')}</th><th>{t('dir')}</th><th>{t('range90')}</th><th aria-hidden="true" /></tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.key}>
              <th scope="row"><AssetLink k={r.key}>{nm(r)}</AssetLink>{r.name !== r.key && <span className="muted code"> {r.key}</span>}</th>
              <td className="nowrap">{money(r.price, r.decimals, r.unit)}</td>
              <td>{pct(r.chg1d)}</td>
              <td className="nowrap"><Glyph d={r.direction} /> {Math.round(r.p_up * 100)}% <span className="muted">{t(r.direction)}</span></td>
              <td className="nowrap">{money(r.q05, r.decimals, r.unit)} - {num(r.q95, r.decimals)}</td>
              <td><Spark values={r.spark} label={`${nm(r)}: ${t('chart_hist')}`} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HorizonPicker({value, onChange}: {value: string; onChange: (h: string) => void}) {
  const {t} = useT();
  const names: Record<string, [string, string]> = {'1h': ['1 jam', '1 hour'], '4h': ['4 jam', '4 hours'], '1d': ['1 hari', '1 day'],
    '1w': ['1 minggu', '1 week'], '2w': ['2 minggu', '2 weeks'], '3w': ['3 minggu', '3 weeks'], '1m': ['1 bulan', '1 month']};
  const {lang} = useT();
  return (
    <Selector label={t('horizon')} value={value} onChange={onChange} width={180}
      options={HORIZONS.map(h => ({value: h, label: names[h][lang === 'id' ? 0 : 1]}))} />
  );
}

export function Markets({onAuth, kind}: PageProps & {kind: 'fx' | 'stocks'}) {
  const {t, l} = useT();
  const [h, setH] = useState('1w');
  const [tab, setTab] = useState(kind === 'fx' ? 'fx' : 'recs');
  const group = tab === 'recs' ? null : tab;
  const rows = useLoad(() => (group ? api.markets(group, h) : Promise.resolve({rows: []})), [group, h], onAuth);
  const usd = useLoad(() => (kind === 'fx' ? api.asset('USDIDR', h) : Promise.resolve(null)), [kind, h], onAuth);
  return (
    <>
      <header className="page-head">
        <Heading level={1}>{t(kind === 'fx' ? 'fx_title' : 'stocks_title')}</Heading>
        {kind === 'fx' && <p className="lead">{t('fx_lead')}</p>}
      </header>
      <div className="toolbar">
        {kind === 'fx' ? (
          <SegmentedControl label={t('market')} value={tab} onChange={setTab}>
            <SegmentedControlItem value="fx" label={t('nav_fx')} />
            <SegmentedControlItem value="commodity" label={t('tab_comm')} />
          </SegmentedControl>
        ) : (
          <SegmentedControl label={t('market')} value={tab} onChange={setTab}>
            <SegmentedControlItem value="recs" label={t('tab_recs')} />
            <SegmentedControlItem value="index" label={t('indices')} />
            <SegmentedControlItem value="stock_id" label={t('tab_id')} />
            <SegmentedControlItem value="stock_us" label={t('tab_us')} />
          </SegmentedControl>
        )}
        {group && <HorizonPicker value={h} onChange={setH} />}
      </div>
      {kind === 'fx' && tab === 'fx' && usd.data && (
        <section className="asset first">
          <header className="asset-head"><h3><AssetLink k="USDIDR">USD/IDR</AssetLink></h3></header>
          <Verdict view={usd.data} />
          {usd.data.vigilance && <VigilanceLine v={usd.data.vigilance} decimals={0} horizonName={l(usd.data.horizon_name)} />}
        </section>
      )}
      {group ? <Async state={rows}>{d => <MarketTable rows={d.rows} />}</Async> : <RecsPanel onAuth={onAuth} />}
    </>
  );
}

function RecsPanel({onAuth}: PageProps) {
  const {t} = useT();
  const state = useLoad(api.recs, [], onAuth);
  return (
    <Async state={state}>
      {recs => (
        <>
          {(['ID', 'US'] as const).map(m => (
            <section key={m} aria-labelledby={`rec-${m}`}>
              <h2 id={`rec-${m}`} className="section-h">{t(m === 'ID' ? 'market_id' : 'market_us')}</h2>
              {recs[m].length === 0 ? (
                recs.screened[m] === 0
                  ? <EmptyState isCompact title={t('recs_wait_title')} description={t('recs_wait_desc')} />
                  : <EmptyState isCompact title={t('no_recs_title')} description={t('no_recs_desc', {n: recs.screened[m]})} />
              ) : (
                <div className="rec-list">{recs[m].map(c => <RecCardView key={c.key} c={c} />)}</div>
              )}
            </section>
          ))}
          <p className="note">{t('recs_note')}</p>
        </>
      )}
    </Async>
  );
}

function RecCardView({c}: {c: RecCard}) {
  const {t, l, num, money, pct} = useT();
  const d = c.decimals;
  const u = c.unit;
  return (
    <Card>
      <article className="rec">
        <header className="asset-head">
          <h3><AssetLink k={c.key}>{c.key}</AssetLink> <span className="muted">{c.name}</span></h3>
          <span className="price">{money(c.price, d, u)}</span>
          <span className="change">{pct(c.chg1d)} <span className="muted">{t('today')}</span></span>
        </header>
        <h4 className="label">{t('strengths')}</h4>
        <ol className="strengths">{c.strengths.map((s, i) => <li key={i}>{l(s)}</li>)}</ol>
        <h4 className="label">{t('why_enter')}</h4>
        <p>{l(c.why)}</p>
        <h4 className="label">{t('risks')}</h4>
        <ul className="plain">{c.risks.map((s, i) => <li key={i}>{l(s)}</li>)}</ul>
        <dl className="plan">
          <div><dt>{t('entry')}</dt><dd>{money(c.plan.entry[0], d, u)} - {num(c.plan.entry[1], d)}</dd></div>
          <div><dt>{t('target')}</dt><dd>{money(c.plan.targets[0], d, u)} / {num(c.plan.targets[1], d)}</dd></div>
          <div><dt>{t('stop')}</dt><dd>{money(c.plan.stop, d, u)}</dd></div>
          <div><dt>{t('rr')}</dt><dd>{num(c.plan.rr, 1)} : 1</dd></div>
        </dl>
      </article>
    </Card>
  );
}

function usePoll<T>(fn: () => Promise<T>, everyMs: (d: T | null) => number, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState(false);
  const last = useRef<T | null>(null);
  useEffect(() => {
    let alive = true;
    let timer = 0;
    last.current = null;
    setData(null);
    const tick = async () => {
      if (document.visibilityState === 'visible') {
        try {
          const d = await fn();
          if (alive) { last.current = d; setData(d); setError(false); }
        } catch { if (alive) setError(true); }
      }
      if (alive) timer = window.setTimeout(tick, everyMs(last.current));
    };
    void tick();
    return () => { alive = false; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return {data, error};
}

function LivePanel({k, decimals: fallback, klass}: {k: string; decimals: number; klass: string}) {
  const {t, l, num, money, pct, when} = useT();
  const {data, error} = usePoll(() => api.live(k), d => (d?.realtime ? 5000 : 30000), [k]);
  const decimals = data?.decimals ?? fallback;
  if (!data) return error ? <p className="note">{t('live_off')}</p> : <div className="live-chart is-empty" aria-busy="true" />;
  const up = (data.chg_pct ?? 0) >= 0;
  const goodForOwner = up !== (klass === 'fx');
  return (
    <section className="live" aria-labelledby="live-h">
      <div className="live-head">
        <h2 id="live-h" className="block-h">{t('live_h')}</h2>
        <span className={`live-badge ${data.realtime ? 'is-live' : ''}`}>
          {data.realtime ? t('live_rt', {src: data.source === 'stockbit' ? 'Stockbit' : 'Binance'}) : t('live_delay', {m: data.delay_min ?? 15})}
        </span>
      </div>
      <p className="live-price">
        <span className="price big">{money(data.last, decimals, data.unit)}</span>
        {data.chg_pct != null && <span className={`delta ${goodForOwner ? 'delta-up' : 'delta-down'}`}>{pct(data.chg_pct, 2)} <span className="muted">{t('today')}</span></span>}
        <span className="muted small">{t('updated')} {when(data.at)}</span>
      </p>
      {data.note && <p className="note">{l(data.note)}</p>}
      {data.bars.length > 1 ? <LiveChart bars={data.bars} decimals={decimals} label={t('live_h')} /> : <p className="note">{t('live_closed')}</p>}
      {data.book && (data.book.bids.length > 0 || data.book.offers.length > 0) && (
        <details className="why">
          <summary>{t('orderbook')}</summary>
          <div className="book">
            <table><thead><tr><th>{t('bid_lots')}</th><th>{t('bid')}</th><th>{t('offer')}</th><th>{t('offer_lots')}</th></tr></thead>
              <tbody>{Array.from({length: Math.max(data.book.bids.length, data.book.offers.length)}, (_, i) => (
                <tr key={i}><td>{data.book!.bids[i] ? num(data.book!.bids[i].lots, 0) : ''}</td><td>{data.book!.bids[i] ? num(data.book!.bids[i].price, 0) : ''}</td>
                  <td>{data.book!.offers[i] ? num(data.book!.offers[i].price, 0) : ''}</td><td>{data.book!.offers[i] ? num(data.book!.offers[i].lots, 0) : ''}</td></tr>))}
              </tbody></table>
          </div>
          {data.book.foreign_net != null && <p className="note">{t('foreign_net_today')}: {num(data.book.foreign_net, 0)}</p>}
        </details>
      )}
    </section>
  );
}

function VoteMark({v}: {v: number}) {
  const {t} = useT();
  return <span className="vote">{v > 0 ? '▲' : v < 0 ? '▼' : '–'} {t(v > 0 ? 'v_up' : v < 0 ? 'v_down' : 'v_none')}</span>;
}

function Conclusion({f}: {f: Forecast}) {
  const {t, money, lang} = useT();
  const p = f.conclusion.p_up;
  const upSide = p >= 0.5;
  // Same rule as the home page: at least 60% on the owner's side is good, at most 40% is not good.
  const pGood = Math.round((f.up_is < 0 ? 1 - p : p) * 100);
  const state = pGood >= 60 ? 'good' : pGood <= 40 ? 'bad' : 'neutral';
  const chance = Math.round((upSide ? p : 1 - p) * 100);
  const edge = Math.abs(Math.round(p * 100) - 50);
  const conf = edge >= 10 ? 'c_strong' : edge >= 5 ? 'c_fair' : 'c_thin';
  const d = f.decimals;
  const fx = f.klass === 'fx';
  const side = fx ? (upSide ? t('rupiah_weaker') : t('rupiah_stronger')) : (upSide ? t('v_up_long') : t('v_down_long'));
  return (
    <div className={`conclusion conclusion-${state}`}>
      <p className="conclusion-k">{t('conclusion')} · {f.horizon_name[lang]}</p>
      <p className="conclusion-v">{t(state)}</p>
      <p>{t('concl_line', {side, p: chance, conf: t(conf)})}{state === 'neutral' ? ` ${t('concl_neutral')}` : ''}</p>
      <p>{t('concl_range', {lo: money(f.conclusion.q05, d, f.unit), hi: money(f.conclusion.q95, d, f.unit), mid: money(f.conclusion.q50, d, f.unit)})}</p>
      <p className="note">{t('concl_votes', {up: f.votes.up, down: f.votes.down, none: f.votes.none})}</p>
    </div>
  );
}

function TechniqueList({f}: {f: Forecast}) {
  const {t, l, money, pct} = useT();
  const used = f.techniques.filter(x => x.status.used);
  const shown = f.techniques.filter(x => !x.status.used);
  const row = (x: Technique) => (
    <li key={x.key} className={`tech-row${x.status.used ? ' is-used' : ''}`}>
      <div className="tech-top">
        <strong>{l(x.name)}</strong>
        <span className={`use-tag${x.status.used ? ' is-used' : ''}`}>{t(x.status.used ? 'tag_used' : 'tag_shown')}</span>
        <VoteMark v={x.vote} />
        {x.exp_ret != null && x.target != null && <span className="muted">{money(x.target, f.decimals, f.unit)} ({pct(x.exp_ret)})</span>}
      </div>
      <p><span className="row-k">{t('says_now')}:</span> {l(x.reason)}</p>
      <p><span className="row-k">{t('why_tech')}:</span> {l(x.purpose)}</p>
      <p className="note">
        {l(x.status)}{' '}
        {x.hist && x.hist.hit != null && x.hist.chance != null && x.hist.n_eff >= 12 &&
          t('tested_line', {hit: Math.round(x.hist.hit * 100), chance: Math.round(x.hist.chance * 100), n: x.hist.n_eff})}
      </p>
    </li>
  );
  return (
    <>
      <div className="tech-summary">
        <p><span className="row-k">{t('used_h')}:</span> {used.map(x => l(x.name)).join(', ')}.</p>
        {shown.length > 0 && <p className="muted"><span className="row-k">{t('shown_h')}:</span> {shown.map(x => l(x.name)).join(', ')}.</p>}
      </div>
      <ol className="techs">{used.map(row)}{shown.map(row)}</ol>
    </>
  );
}

export function AssetPage({onAuth, k}: PageProps & {k: string}) {
  const {t, l, nm, money} = useT();
  const [h, setH] = useState<H3>('1m');
  const [hs, setHs] = useState('1w');
  const [custom, setCustom] = useState('');
  const [customErr, setCustomErr] = useState(false);
  const [asking, setAsking] = useState(false);
  const [askErr, setAskErr] = useState<string | null>(null);
  const fc = useLoad(() => api.forecast(k, h), [k, h], onAuth);
  const state = useLoad(() => api.asset(k, hs), [k, hs], onAuth);
  const applyCustom = () => {
    const v = custom.trim().toLowerCase();
    if (/^[1-9]\d{0,2}[hdwm]$/.test(v)) { setCustomErr(false); setHs(v); } else setCustomErr(true);
  };
  const ask = async () => {
    setAsking(true); setAskErr(null);
    try { await api.analyze(k); state.reload(); fc.reload(); }
    catch (e) { setAskErr(e instanceof ApiError && e.status === 409 ? t('team_off') : t('team_failed')); }
    finally { setAsking(false); }
  };
  const view = state.data;
  const f = fc.data;
  const decimals = f?.decimals ?? view?.decimals ?? 2;
  const klass = f?.klass ?? view?.klass ?? '';
  return (
    <>
      <p className="back"><a href="#/">{t('back')}</a></p>
      <header className="page-head">
        <Heading level={1}>{f ? nm(f) : view ? nm(view) : k}</Heading>
      </header>
      <LivePanel k={k} decimals={decimals} klass={klass} />

      <section className="block" aria-labelledby="fc-h">
        <div className="live-head">
          <h2 id="fc-h" className="block-h">{t('forecast_h')}</h2>
          <HorizonTabs value={h} onChange={setH} />
        </div>
        <Async state={fc}>
          {f2 => (
            <div className={fc.loading ? 'is-loading' : ''}>
              <Conclusion f={f2} />
              <ProjectionChart f={f2} />
              <h3 className="label">{t('techs_h')}</h3>
              <p className="note">{t('techs_lead')}</p>
              <TechniqueList f={f2} />
            </div>
          )}
        </Async>
      </section>

      {view && (
        <>
          <details className="why">
            <summary>{t('why_q')}</summary>
            <Reasons items={view.reasons} />
            {view.watch && <p className="watch"><strong>{t('watch')}:</strong> {l(view.watch)}</p>}
            {view.debate && (view.debate.bull || view.debate.bear) && (
              <div className="debate">
                {view.debate.bull && <div><h3 className="label">▲ {t('bull')}</h3><p>{l(view.debate.bull)}</p></div>}
                {view.debate.bear && <div><h3 className="label">▼ {t('bear')}</h3><p>{l(view.debate.bear)}</p></div>}
              </div>
            )}
            {view.sources && view.sources.length > 0 && (
              <>
                <h3 className="label">{t('sources')}</h3>
                <ul className="plain">{view.sources.map((s2, i) => (
                  <li key={i}><a href={s2.url} target="_blank" rel="noopener noreferrer">{s2.title}</a> <span className="muted">{s2.source}</span></li>))}
                </ul>
              </>
            )}
          </details>
          <details className="why">
            <summary>{t('short_h')}</summary>
            {view.horizons && <HorizonStrip rows={view.horizons} selected={view.horizon} onSelect={setHs} />}
            <p className="verdict">{l(view.summary)}</p>
            {view.vigilance && <VigilanceLine v={view.vigilance} decimals={view.decimals} horizonName={l(view.horizon_name)} />}
            {Object.keys(view.forecast.touch).length > 0 && (
              <ul className="plain touch">
                {Object.entries(view.forecast.touch).sort((a2, b2) => Number(a2[0]) - Number(b2[0])).map(([lv, p]) => (
                  <li key={lv}>{t('touch')} {money(Number(lv), view.decimals, view.unit)}: <strong>{Math.round(p * 100)}%</strong></li>
                ))}
              </ul>
            )}
            <FanChart view={view} />
            <GradeNote v={view.validation} />
            {view.notes.map((n, i) => <p key={i} className="note">{l(n)}</p>)}
            <div className="toolbar">
              <TextInput label={t('custom_h')} description={t('custom_h_hint')} value={custom} onChange={setCustom} onEnter={applyCustom}
                width={180} status={customErr ? {type: 'error', message: t('bad_horizon')} : undefined} />
              <Button label={t('apply')} onClick={applyCustom} />
            </div>
          </details>
          {view.llm_enabled ? (
            <div className="actions">
              <Button label={asking ? t('asking') : t('ask_team')} variant="primary" onClick={ask} isLoading={asking} />
            </div>
          ) : <p className="note">{t('team_off')}</p>}
          {askErr && <Banner status="warning" title={askErr} />}
        </>
      )}
    </>
  );
}

export function World({onAuth}: PageProps) {
  const {t, l, when} = useT();
  const state = useLoad(api.brief, [], onAuth);
  const [c, setC] = useState('ID');
  return (
    <>
      <header className="page-head"><Heading level={1}>{t('world_title')}</Heading><p className="lead">{t('world_lead')}</p></header>
      <Async state={state}>
        {({brief}) => !brief ? <EmptyState title={t('no_brief_title')} description={t('no_brief_desc')} /> : (
          <>
            <div className="toolbar">
              <SegmentedControl label={t('country')} value={c} onChange={setC}>
                {Object.entries(brief.countries).map(([k, v]) => <SegmentedControlItem key={k} value={k} label={l(v.name)} />)}
              </SegmentedControl>
            </div>
            {(() => {
              const d = brief.countries[c];
              return (
                <section>
                  {d.summary ? <p className="verdict">{l(d.summary)}</p> : <p className="note">{t('desk_off')}</p>}
                  {d.events.map((e, i) => (
                    <article key={i} className="event">
                      <h3>{l(e.what)}</h3>
                      <p><strong>{t('effect')}:</strong> {l(e.effect)}</p>
                      <ul className="plain small">{e.sources.map((s, j) => (
                        <li key={j}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> <span className="muted">{s.source}</span></li>))}
                      </ul>
                    </article>
                  ))}
                  <h2 className="section-h">{t('headlines')}</h2>
                  {d.headlines.length === 0 ? <p className="note">{t('no_news')}</p> : (
                    <ul className="plain">{d.headlines.map((n, i) => (
                      <li key={i}><a href={n.url} target="_blank" rel="noopener noreferrer">{n.title}</a> <span className="muted">{n.source} · {when(n.at)}</span></li>))}
                    </ul>
                  )}
                </section>
              );
            })()}
          </>
        )}
      </Async>
    </>
  );
}

export function TrackPage({onAuth}: PageProps) {
  const {t, l, nm, num} = useT();
  const state = useLoad(api.track, [], onAuth);
  const mark = {validated: '●', range_only: '◐', experimental: '○', insufficient: '·'} as const;
  return (
    <>
      <header className="page-head"><Heading level={1}>{t('track_title')}</Heading><p className="lead">{t('track_lead')}</p></header>
      <Async state={state}>
        {d => (
          <>
            <h2 className="section-h">{t('live')}</h2>
            {d.live.scored === 0 ? <p className="note">{t('live_empty')}</p> : (
              <div className="scroll-x">
                <table className="market">
                  <thead><tr><th>{t('horizon')}</th><th>{t('scored')}</th><th>{t('calls')}</th><th>{t('in_range')}</th></tr></thead>
                  <tbody>{d.live.by_horizon.filter(r => r.n > 0).map(r => (
                    <tr key={r.horizon}><th scope="row">{l(r.name)}</th><td>{r.n}</td>
                      <td>{r.calls ? `${r.call_hits} / ${r.calls}` : '-'}</td>
                      <td>{r.cover90 == null ? '-' : `${num(r.cover90 * 100, 0)}%`}</td></tr>))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="note">{t('pending_n', {n: d.live.pending})}</p>

            <h2 className="section-h">{t('hist')}</h2>
            <p>{t('hist_lead')}</p>
            {d.validating && <Banner status="info" title={t('hist_running')} />}
            <p className="note">● {t('legend_ok')} · ◐ {t('legend_range')} · ○ {t('legend_exp')}</p>
            <div className="scroll-x">
              <table className="market grid">
                <thead><tr><th>{t('asset')}</th>{HORIZONS.map(h => <th key={h}>{h}</th>)}</tr></thead>
                <tbody>{d.tests.map(row => (
                  <tr key={row.key}><th scope="row">{nm(row)}</th>
                    {HORIZONS.map(h => {
                      const v = row.horizons[h];
                      return <td key={h} title={v?.cover90 != null ? `${t('in_range')}: ${num(v.cover90 * 100, 0)}%` : undefined}>
                        {v ? <span role="img" aria-label={t(`g_${v.grade}` as const)}>{mark[v.grade]}</span> : ''}
                        {v?.hit_rate != null && <span className="muted small"> {num(v.hit_rate * 100, 0)}%</span>}
                      </td>;
                    })}
                  </tr>))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Async>
    </>
  );
}

export function SettingsPage({onAuth, onLang, authRequired}: PageProps & {onLang: (l: Lang) => void; authRequired: boolean}) {
  const {t, num, money, when, lang} = useT();
  const status = useLoad(api.status, [], onAuth);
  const prefs = useLoad(api.settings, [], onAuth);
  const alerts = useLoad(api.alerts, [], onAuth);
  const [levels, setLevels] = useState('');
  const [saved, setSaved] = useState(false);
  const [aKey, setAKey] = useState('USDIDR');
  const [aOp, setAOp] = useState('>');
  const [aLevel, setALevel] = useState('');
  useEffect(() => { if (prefs.data) setLevels((prefs.data.levels.USDIDR ?? []).join(', ')); }, [prefs.data]);
  const parse = (s: string) => Number(s.replace(/\s/g, '').replace(lang === 'id' ? /\./g : /,/g, '').replace(',', '.'));
  const saveLevels = async () => {
    const vals = levels.split(/[,;]\s*|\s+/).map(parse).filter(v => v > 0);
    await api.saveSettings({levels: {...(prefs.data?.levels ?? {}), USDIDR: vals}});
    setSaved(true); prefs.reload();
  };
  const addAlert = async () => {
    const v = parse(aLevel);
    if (!(v > 0)) return;
    await api.addAlert(aKey, aOp, v); setALevel(''); alerts.reload();
  };
  return (
    <>
      <header className="page-head"><Heading level={1}>{t('settings_title')}</Heading></header>
      <section className="form">
        <SegmentedControl label={t('language')} value={lang} onChange={v => onLang(v as Lang)}>
          <SegmentedControlItem value="id" label="Bahasa Indonesia" />
          <SegmentedControlItem value="en" label="English" />
        </SegmentedControl>
      </section>

      <h2 className="section-h">{t('levels')}</h2>
      <div className="toolbar">
        <TextInput label="USD/IDR" description={t('levels_desc')} value={levels} onChange={v => { setLevels(v); setSaved(false); }} width="100%" />
        <Button label={t('save')} onClick={saveLevels} />
      </div>
      {saved && <p className="note" role="status">{t('saved')}</p>}

      <h2 className="section-h">{t('alerts')}</h2>
      <div className="toolbar">
        <Selector label={t('asset')} value={aKey} onChange={setAKey} hasSearch width={200}
          options={(prefs.data?.assets ?? []).map(a => ({value: a.key, label: `${a.key} ${a.name === a.key ? '' : a.name}`.trim()}))} />
        <Selector label={t('dir')} value={aOp} onChange={setAOp} width={130}
          options={[{value: '>', label: t('above')}, {value: '<', label: t('below')}]} />
        <TextInput label={t('level')} value={aLevel} onChange={setALevel} onEnter={addAlert} width={140} inputMode="decimal" />
        <Button label={t('add_alert')} onClick={addAlert} />
      </div>
      <Async state={alerts}>
        {d => d.items.length === 0 ? <p className="note">{t('no_alerts')}</p> : (
          <ul className="plain alerts">{d.items.map(a => (
            <li key={a.id}>
              <span>{a.name} {a.op === '>' ? t('above') : t('below')} {money(a.level, a.decimals, a.unit)}
                {a.triggered_at && <> <Badge variant="warning" label={t('triggered')} /> <span className="muted">{when(a.triggered_at)}</span></>}</span>
              <Button label={t('remove')} size="sm" variant="ghost" onClick={async () => { await api.delAlert(a.id); alerts.reload(); }} />
            </li>))}
          </ul>
        )}
      </Async>

      <h2 className="section-h">{t('system')}</h2>
      <Async state={status}>
        {s => (
          <dl className="plan wide">
            <div><dt>{t('data_at')}</dt><dd>{when(s.data_at) || '-'}</dd></div>
            <div><dt>{t('ai_team')}</dt><dd>{s.llm_enabled ? `${t('on')}: ${s.models.provider} (${s.models.quick}, ${s.models.deep})` : t('off')}{s.models.fallback ? ` · ${t('fallback')}: ${s.models.fallback}` : ''}{s.llm_last ? ` · ${t('last_used')}: ${s.llm_last.provider}` : ''}{s.claude_calls_today ? ` · ${s.claude_calls_today} ${t('calls_today')}` : ''}</dd></div>
            <div><dt>{t('budget')}</dt><dd>${num(s.budget.month, 2)} / ${num(s.budget.cap_month, 0)}</dd></div>
            <div><dt>Stockbit</dt><dd>{!s.stockbit?.configured ? t('sb_off') : s.stockbit.usable ? t('sb_on', {d: when(s.stockbit.refresh_until ?? null)}) : t('sb_expired')}</dd></div>
            <div><dt>{t('telegram')}</dt><dd>{s.telegram_enabled ? t('on') : t('off')}</dd></div>
            <div><dt>{t('schedule')} ({s.timezone})</dt><dd>{s.schedule.map(x => x.time).join(' · ')}</dd></div>
            {Object.keys(s.data_errors).length > 0 && <div><dt>{t('data_errors')}</dt><dd>{Object.keys(s.data_errors).join(', ')}</dd></div>}
            <div><dt>{t('recs_status')}</dt><dd>{s.recs?.at
              ? t('recs_status_v', {id: s.recs.screened?.ID ?? 0, us: s.recs.screened?.US ?? 0, at: when(s.recs.at)})
              : t('recs_status_none')}</dd></div>
            <div><dt>ARAH</dt><dd>{s.version}{s.revision && s.revision !== 'unknown' ? ` · ${s.revision}` : ''}</dd></div>
          </dl>
        )}
      </Async>
      {authRequired && <div className="actions"><Button label={t('logout')} onClick={async () => { await api.logout(); onAuth(); }} /></div>}
    </>
  );
}

export function Login({onDone}: {onDone: () => void}) {
  const {t} = useT();
  const [pw, setPw] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true); setErr(null);
    try { await api.login(pw); onDone(); }
    catch (e) { setErr(e instanceof ApiError && e.status === 429 ? t('too_many') : t('wrong_pw')); }
    finally { setBusy(false); }
  };
  return (
    <main className="login">
      <form className="login-card" onSubmit={e => { e.preventDefault(); void submit(); }}>
        <header className="login-brand">
          <span className="lrm-mark full" role="img" aria-label="Liando Reyfort Management" />
          <h1 className="login-title">ARAH <span className="brand-by">by LRM</span></h1>
          <p className="note">{t('login_title')}</p>
        </header>
        <TextInput type="password" label={t('password')} value={pw} onChange={setPw} autoComplete="current-password" hasAutoFocus
          status={err ? {type: 'error', message: err} : undefined} width="100%" />
        <Button type="submit" variant="primary" label={t('login')} isLoading={busy} width="100%" size="lg" />
      </form>
    </main>
  );
}
