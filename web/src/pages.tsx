import {useEffect, useState, type ReactNode} from 'react';
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
import {api, ApiError, type Answer, type Brief, type Calc, type Lang, type MarketRow, type RecCard, type Simple, type SimpleCard, type State} from './api';
import {FanChart, Spark} from './charts';
import {AssetLink, Async, Change, Glyph, GradeNote, HorizonStrip, Reasons, Verdict, VigilanceLine} from './components';
import {useLoad} from './hooks';
import {useT} from './i18n';

interface PageProps {onAuth: () => void}
const HORIZONS = ['1h', '4h', '1d', '1w', '2w', '3w', '1m'];

function Pill({label, state, name}: {label: string; state: State; name: string}) {
  return (
    <span className={`pill pill-${state}`}>
      <span className="pill-k">{label}</span>
      <span className="pill-v">{name}</span>
    </span>
  );
}

/** One question, two answers (now, next month), one reason. "Why?" opens the rest. */
function Answer({id, title, sub, card, extra}: {id: string; title: string; sub: string; card: SimpleCard; extra?: ReactNode}) {
  const {t, l, num} = useT();
  return (
    <section className="answer" aria-labelledby={id}>
      <h2 id={id} className="answer-h">{title}</h2>
      <p className="note">{sub}</p>
      <div className="pills">
        <Pill label={t('now')} state={card.now.state} name={l(card.now.name)} />
        <Pill label={t('next_month')} state={card.next.state} name={l(card.next.name)} />
      </div>
      <p className="answer-line">{l(card.now.text)}</p>
      <p className="answer-line">{l(card.next.text)}</p>
      {card.bca && <p className="note">{t('bca_line', {buy: num(card.bca.buy, card.bca.buy < 1000 ? 2 : 0), sell: num(card.bca.sell, card.bca.sell < 1000 ? 2 : 0)})}</p>}
      {extra}
      <WhyBox card={card} />
    </section>
  );
}

function WhyBox({card}: {card: SimpleCard}) {
  const {t, l, num} = useT();
  return (
    <details className="why">
      <summary>{t('why_q')}</summary>
      <Reasons items={card.reasons} />
      {card.watch && <p className="watch"><strong>{t('watch')}:</strong> {l(card.watch)}</p>}
      {Object.entries(card.touch).length > 0 && (
        <p className="note">{Object.entries(card.touch).sort((x, y) => Number(x[0]) - Number(y[0])).map(([lv, p]) =>
          `${t('touch')} ${num(Number(lv), card.decimals)}: ${Math.round(p * 100)}%`).join(' · ')}</p>
      )}
      <p className="note">{t(card.from_team ? 'by_team' : 'by_rules')} {card.grade ? t(`g_${card.grade}` as const) : ''}</p>
      <p className="more"><a href={`#/a/${card.key}`}>{t('open_chart')}</a></p>
    </details>
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

function Summary({brief, simple, building, rebuild, canAsk}: {brief: Brief; simple: Simple; building: boolean; rebuild: () => void; canAsk: boolean}) {
  const {t, l, nm, when} = useT();
  const rep = brief.report;
  const dayOf = (ts: number) => new Intl.DateTimeFormat(undefined, {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'}).format(ts * 1000);
  const ab = simple.abroad;
  return (
    <>
      <header className="lede">
        <p className="kicker">{t('updated')} {when(brief.at)}</p>
        <h1 className="headline">{l(brief.headline)}</h1>
        {brief.outlook && <p className="verdict"><strong>{t('my_view')}:</strong> {l(brief.outlook)}</p>}
      </header>

      {simple.indonesia && (
        <Answer id="q-id" title={t('q_id')} sub={t('sub_id')} card={simple.indonesia} extra={brief.foreign && (
          <p className="answer-line"><strong>{t(brief.foreign.side === 'buy' ? 'foreign_buy' : 'foreign_sell')}.</strong> {l(brief.foreign.text)}{' '}
            {brief.foreign.sources[0] && <a className="muted" href={brief.foreign.sources[0].url} target="_blank" rel="noopener noreferrer">{brief.foreign.sources[0].source}</a>}</p>
        )} />
      )}

      {ab && (
        <section className="answer" aria-labelledby="q-ab">
          <h2 id="q-ab" className="answer-h">{t('q_abroad')}</h2>
          <p className="note">{t('sub_abroad')}</p>
          <div className="pills">
            <Pill label={t('now')} state={ab.now.state} name={l(ab.now.name)} />
            <Pill label={t('next_month')} state={ab.next.state} name={l(ab.next.name)} />
          </div>
          <p className="answer-line">{l(ab.now.text)}</p>
          <ul className="countries">
            {ab.countries.map(c => (
              <li key={c.key}>
                <div className="country-head">
                  <strong>{t(`c_${c.country}` as 'c_US')}</strong> <span className="muted">{nm(c)}</span>
                  <span className="pills small">
                    <Pill label={t('now')} state={c.now.state} name={l(c.now.name)} />
                    <Pill label={t('next_month')} state={c.next.state} name={l(c.next.name)} />
                  </span>
                </div>
                <WhyBox card={c} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {simple.usd && <Answer id="q-usd" title={t('q_usd')} sub={t('sub_fx')} card={simple.usd} />}
      {simple.cny && <Answer id="q-cny" title={t('q_cny')} sub={t('sub_fx')} card={simple.cny} />}

      <section className="answer" aria-labelledby="q-ev">
        <h2 id="q-ev" className="answer-h">{t('events_h')}</h2>
        {(brief.events ?? []).length === 0 ? <p className="note">{t('no_events')}</p> : (
          <ul className="events">
            {(brief.events ?? []).map((e, i) => (
              <li key={i}>
                <span className="event-when">{dayOf(e.at)} · {t(`c_${e.country}` as 'c_US')}</span>
                <strong>{e.title ?? l(e.what)}</strong>
                {e.why ? <span>{l(e.why)}</span> : <span className="muted">{t('from_news')}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      {canAsk && <AskBox />}

      <p className="note mode">
        {rep && rep.total > 0 ? t('report_line', {right: rep.right, wrong: rep.wrong}) : t('report_none')}{' '}
        {t(brief.mode === 'team' ? 'mode_team' : 'mode_rules')}
      </p>
      <div className="actions">
        <Button label={building ? t('building') : t('refresh_brief')} onClick={rebuild} isLoading={building} />
      </div>
    </>
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
    <section className="answer" aria-labelledby="q-ask">
      <h2 id="q-ask" className="answer-h">{t('ask_h')}</h2>
      <div className="toolbar">
        <TextInput label={t('ask_label')} placeholder={t('ask_ph')} value={q} onChange={setQ} onEnter={send} width="100%"
          status={err ? {type: 'error', message: err} : undefined} />
        <Button label={t('ask_btn')} variant="primary" onClick={send} isLoading={busy} />
      </div>
      {a && (
        <div aria-live="polite">
          <div className="pills"><Pill label={`${t('conf')} ${t(`c_${a.confidence}` as const)}`} state={a.verdict} name={t(a.verdict)} /></div>
          <p className="verdict">{l(a.answer)}</p>
          <Reasons items={a.points} />
          {a.risk && <p className="watch"><strong>{t('risk_one')}:</strong> {l(a.risk)}</p>}
        </div>
      )}
    </section>
  );
}

export function CalcPage({onAuth}: PageProps) {
  const {t, l, num, when, lang} = useT();
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
          <p className="answer-line">{t('rate')}: {num(c.rate, 2)} ({t(c.source === 'bca' ? 'rate_bca' : 'rate_market')}{c.rate_at ? `, ${when(c.rate_at)}` : ''})</p>
          <p className="answer-line">{t('in_month')} {num(c.next_low, 2)} {t('to')} {num(c.next_high, 2)} {c.currency}.</p>
          <p className="answer-line"><strong>{l(c.advice)}</strong></p>
        </section>
      )}
    </>
  );
}

function MarketTable({rows}: {rows: MarketRow[]}) {
  const {t, nm, num, pct} = useT();
  return (
    <div className="scroll-x">
      <table className="market">
        <thead><tr><th>{t('name')}</th><th>{t('price')}</th><th>{t('today')}</th><th>{t('dir')}</th><th>{t('range90')}</th><th aria-hidden="true" /></tr></thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.key}>
              <th scope="row"><AssetLink k={r.key}>{nm(r)}</AssetLink>{r.name !== r.key && <span className="muted code"> {r.key}</span>}</th>
              <td>{num(r.price, r.decimals)}</td>
              <td>{pct(r.chg1d)}</td>
              <td className="nowrap"><Glyph d={r.direction} /> {Math.round(r.p_up * 100)}% <span className="muted">{t(r.direction)}</span></td>
              <td className="nowrap">{num(r.q05, r.decimals)} - {num(r.q95, r.decimals)}</td>
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
                <EmptyState isCompact title={t('no_recs_title')} description={t('no_recs_desc', {n: recs.screened[m]})} />
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
  const {t, l, num, pct} = useT();
  const d = c.decimals;
  return (
    <Card>
      <article className="rec">
        <header className="asset-head">
          <h3><AssetLink k={c.key}>{c.key}</AssetLink> <span className="muted">{c.name}</span></h3>
          <span className="price">{num(c.price, d)}</span>
          <span className="change">{pct(c.chg1d)} <span className="muted">{t('today')}</span></span>
        </header>
        <h4 className="label">{t('strengths')}</h4>
        <ol className="strengths">{c.strengths.map((s, i) => <li key={i}>{l(s)}</li>)}</ol>
        <h4 className="label">{t('why_enter')}</h4>
        <p>{l(c.why)}</p>
        <h4 className="label">{t('risks')}</h4>
        <ul className="plain">{c.risks.map((s, i) => <li key={i}>{l(s)}</li>)}</ul>
        <dl className="plan">
          <div><dt>{t('entry')}</dt><dd>{num(c.plan.entry[0], d)} - {num(c.plan.entry[1], d)}</dd></div>
          <div><dt>{t('target')}</dt><dd>{num(c.plan.targets[0], d)} / {num(c.plan.targets[1], d)}</dd></div>
          <div><dt>{t('stop')}</dt><dd>{num(c.plan.stop, d)}</dd></div>
          <div><dt>{t('rr')}</dt><dd>{num(c.plan.rr, 1)} : 1</dd></div>
        </dl>
      </article>
    </Card>
  );
}

export function AssetPage({onAuth, k}: PageProps & {k: string}) {
  const {t, l, nm, num} = useT();
  const [h, setH] = useState('1w');
  const [custom, setCustom] = useState('');
  const [customErr, setCustomErr] = useState(false);
  const [asking, setAsking] = useState(false);
  const [askErr, setAskErr] = useState<string | null>(null);
  const state = useLoad(() => api.asset(k, h), [k, h], onAuth);
  const applyCustom = () => {
    const v = custom.trim().toLowerCase();
    if (/^[1-9]\d{0,2}[hdwm]$/.test(v)) { setCustomErr(false); setH(v); } else setCustomErr(true);
  };
  const ask = async () => {
    setAsking(true); setAskErr(null);
    try { await api.analyze(k); state.reload(); }
    catch (e) { setAskErr(e instanceof ApiError && e.status === 409 ? t('team_off') : t('team_failed')); }
    finally { setAsking(false); }
  };
  return (
    <>
      <p className="back"><a href="#/">{t('back')}</a></p>
      <Async state={state}>
        {view => (
          <>
            <header className="page-head">
              <Heading level={1}>{nm(view)}</Heading>
              <p className="asset-head">
                <span className="price big">{num(view.forecast.s0, view.decimals)}</span>
                <Change value={view.snapshot.chg1d} label={t('today')} />
                <Change value={view.snapshot.chg1w} label={t('week')} />
                <Change value={view.snapshot.chg1m} label={t('month')} />
              </p>
            </header>
            {view.horizons && <HorizonStrip rows={view.horizons} selected={view.horizon} onSelect={setH} />}
            <div className="toolbar">
              <TextInput label={t('custom_h')} description={t('custom_h_hint')} value={custom} onChange={setCustom} onEnter={applyCustom}
                width={180} status={customErr ? {type: 'error', message: t('bad_horizon')} : undefined} />
              <Button label={t('apply')} onClick={applyCustom} />
            </div>
            <p className="verdict">{l(view.summary)}</p>
            {view.vigilance && <VigilanceLine v={view.vigilance} decimals={view.decimals} horizonName={l(view.horizon_name)} />}
            {Object.keys(view.forecast.touch).length > 0 && (
              <ul className="plain touch">
                {Object.entries(view.forecast.touch).sort((a, b) => Number(a[0]) - Number(b[0])).map(([lv, p]) => (
                  <li key={lv}>{t('touch')} {num(Number(lv), view.decimals)}: <strong>{Math.round(p * 100)}%</strong></li>
                ))}
              </ul>
            )}
            <GradeNote v={view.validation} />
            {view.notes.map((n, i) => <p key={i} className="note">{l(n)}</p>)}
            <FanChart view={view} />
            <h2 className="section-h">{t('why')}</h2>
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
                <ul className="plain">{view.sources.map((s, i) => (
                  <li key={i}><a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a> <span className="muted">{s.source}</span></li>))}
                </ul>
              </>
            )}
            {view.llm_enabled ? (
              <div className="actions">
                <Button label={asking ? t('asking') : t('ask_team')} variant="primary" onClick={ask} isLoading={asking} />
              </div>
            ) : <p className="note">{t('team_off')}</p>}
            {askErr && <Banner status="warning" title={askErr} />}
          </>
        )}
      </Async>
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

export function SettingsPage({onAuth, onLang, themeMode, onTheme, authRequired}: PageProps & {
  onLang: (l: Lang) => void; themeMode: string; onTheme: (m: string) => void; authRequired: boolean}) {
  const {t, num, when, lang} = useT();
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
        <SegmentedControl label={t('theme')} value={themeMode} onChange={onTheme}>
          <SegmentedControlItem value="system" label={t('theme_system')} />
          <SegmentedControlItem value="light" label={t('theme_light')} />
          <SegmentedControlItem value="dark" label={t('theme_dark')} />
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
              <span>{a.name} {a.op === '>' ? t('above') : t('below')} {num(a.level, a.decimals)}
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
            <div><dt>{t('telegram')}</dt><dd>{s.telegram_enabled ? t('on') : t('off')}</dd></div>
            <div><dt>{t('schedule')} ({s.timezone})</dt><dd>{s.schedule.map(x => x.time).join(' · ')}</dd></div>
            {Object.keys(s.data_errors).length > 0 && <div><dt>{t('data_errors')}</dt><dd>{Object.keys(s.data_errors).join(', ')}</dd></div>}
            <div><dt>ARAH</dt><dd>{s.version}</dd></div>
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
      <form onSubmit={e => { e.preventDefault(); void submit(); }}>
        <Heading level={1}>{t('login_title')}</Heading>
        <TextInput type="password" label={t('password')} value={pw} onChange={setPw} autoComplete="current-password" hasAutoFocus
          status={err ? {type: 'error', message: err} : undefined} width="100%" />
        <Button type="submit" variant="primary" label={t('login')} isLoading={busy} width="100%" />
      </form>
    </main>
  );
}
