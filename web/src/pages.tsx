import {useEffect, useState} from 'react';
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
import {api, ApiError, type AssetView, type Brief, type Lang, type MarketRow, type RecCard} from './api';
import {FanChart, Spark} from './charts';
import {AssetLink, Async, Change, Glyph, GradeNote, HorizonStrip, Reasons, Verdict, VigilanceLine} from './components';
import {useLoad} from './hooks';
import {useT} from './i18n';

interface PageProps {onAuth: () => void}
const HORIZONS = ['1h', '4h', '1d', '1w', '2w', '3w', '1m'];

function AssetSection({view}: {view: AssetView}) {
  const {t, l, nm, num} = useT();
  return (
    <section className="asset" aria-labelledby={`a-${view.key}`}>
      <header className="asset-head">
        <h3 id={`a-${view.key}`}><AssetLink k={view.key}>{nm(view)}</AssetLink></h3>
        <span className="price">{num(view.forecast.s0, view.decimals)}</span>
        <Change value={view.snapshot.chg1d} label={t('today')} />
        <Change value={view.snapshot.chg1w} label={t('week')} />
      </header>
      <Verdict view={view} />
      {view.horizons && <HorizonStrip rows={view.horizons} />}
      {view.vigilance && <VigilanceLine v={view.vigilance} decimals={view.decimals} horizonName={l(view.horizon_name)} />}
      <h4 className="label">{t('why')}</h4>
      <Reasons items={view.reasons.slice(0, 3)} />
      {view.watch && <p className="watch"><strong>{t('watch')}:</strong> {l(view.watch)}</p>}
      <p className="more"><a href={`#/a/${view.key}`}>{t('details')}: {nm(view)}</a></p>
    </section>
  );
}

export function Today({onAuth}: PageProps) {
  const {t} = useT();
  const state = useLoad(api.brief, [], onAuth);
  const [busy, setBusy] = useState(false);
  const building = busy || !!state.data?.building;
  useEffect(() => {
    if (!building && state.data?.brief) return;
    const id = window.setInterval(state.reload, 5000);
    return () => window.clearInterval(id);
  }, [building, state.data?.brief, state.reload]);
  useEffect(() => { if (state.data && !state.data.building) setBusy(false); }, [state.data]);

  const rebuild = async () => { setBusy(true); try { await api.runBrief(); } finally { state.reload(); } };

  return (
    <Async state={state}>
      {({brief, llm_error}) => !brief ? (
        <EmptyState title={t('no_brief_title')} description={t('no_brief_desc')} actions={<Spinner size="md" />} />
      ) : (
        <>
          {llm_error && <Banner status="warning" title={t(`llm_${llm_error}` as const)} />}
          <BriefBody brief={brief} building={building} rebuild={rebuild} />
        </>
      )}
    </Async>
  );
}

function BriefBody({brief, building, rebuild}: {brief: Brief; building: boolean; rebuild: () => void}) {
  const {t, l, nm, num, pct, when} = useT();
  return (
    <>
      <header className="lede">
        <p className="kicker">{t('updated')} {when(brief.at)}</p>
        <h1 className="headline">{l(brief.headline)}</h1>
        <p className="note">{t(brief.mode === 'team' ? 'mode_team' : 'mode_rules')}</p>
      </header>

      <section aria-labelledby="world-h">
        <h2 id="world-h" className="section-h">{t('world_dir')}: {l(brief.world.name)}</h2>
        <p className="verdict">{l(brief.world.summary)}</p>
        <ul className="reasons">
          {brief.world.points.map((p, i) => <li key={i}><span className="mark">•</span><span>{l(p.text)}</span></li>)}
        </ul>
        <details className="chart-table">
          <summary>{t('show_numbers')}</summary>
          <div className="scroll-x">
            <table className="tiles">
              <thead><tr><th>{t('market')}</th><th>{t('price')}</th><th>{t('today')}</th><th>{t('week')}</th></tr></thead>
              <tbody>
                {brief.tiles.map(x => (
                  <tr key={x.key}><th scope="row">{nm(x)}</th><td>{num(x.price, x.decimals)}</td><td>{pct(x.chg1d)}</td><td>{pct(x.chg1w)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      {brief.assets.map(v => <AssetSection key={v.key} view={v} />)}

      <div className="actions">
        <Button label={building ? t('building') : t('refresh_brief')} onClick={rebuild} isLoading={building} />
      </div>
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
