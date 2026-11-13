import {useEffect, useRef, useState} from 'react';
import {Banner} from '@astryxdesign/core/Banner';
import {Button} from '@astryxdesign/core/Button';
import {Heading} from '@astryxdesign/core/Heading';
import {SegmentedControl, SegmentedControlItem} from '@astryxdesign/core/SegmentedControl';
import {TextInput} from '@astryxdesign/core/TextInput';
import {api, ApiError, type SbTerminal, type Lang} from './api';
import {LiveChart} from './charts';
import {Async} from './components';
import {StoryList} from './news';
import {useLoad} from './hooks';
import {useT} from './i18n';

interface PageProps {onAuth: () => void}
const HORIZONS = ['1h', '4h', '1d', '1w', '2w', '3w', '1m'];

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

/** Broker and foreign flow, insider filings and busy community posts, from the owner's Stockbit terminal.
 *  Shown only for Indonesian stocks and indices, and only when Stockbit is set up; otherwise it stays out of the way. */
export function FlowPanel({k}: {k: string}) {
  const {t, l, num} = useT();
  const [d, setD] = useState<SbTerminal | null>(null);
  useEffect(() => {
    let live = true;
    api.stockbit(k).then(x => { if (live) setD(x); }).catch(() => { if (live) setD(null); });
    return () => { live = false; };
  }, [k]);
  if (!d || (!d.bandar && !d.foreign && !d.insider?.length && !d.stream?.length)) return null;
  // Rupiah in words people use: T for trillion (triliun), M for billion (miliar).
  const rp = (x: number) => (Math.abs(x) >= 1e12 ? `Rp ${num(Math.abs(x) / 1e12, 2)} T` : `Rp ${num(Math.abs(x) / 1e9, 1)} M`);
  const side = d.bandar?.side ?? 0;
  const tone = side > 0 ? 'good' : side < 0 ? 'bad' : 'neutral';
  const nf = d.foreign?.net_foreign;
  const recent = (d.insider ?? []).slice(0, 3);
  return (
    <section className="block" aria-labelledby="flow-h">
      <h2 id="flow-h" className="block-h">{t('flow_h')}</h2>
      <dl className="plan wide">
        {d.bandar?.label && <div><dt>{t('flow_bandar')}</dt><dd>
          <span className={`chip chip-${tone}`}>{d.bandar.label}</span>
          {d.bandar.top5?.label && <span className="muted"> · top 5: {d.bandar.top5.label}</span>}
          {d.bandar.buyers != null && d.bandar.sellers != null && <span className="muted"> · {t('flow_bs', {b: d.bandar.buyers, s: d.bandar.sellers})}</span>}
        </dd></div>}
        {nf != null && <div><dt>{t('flow_foreign')}</dt><dd>
          <span className={`delta ${nf >= 0 ? 'delta-up' : 'delta-down'}`}>{nf >= 0 ? t('flow_net_buy') : t('flow_net_sell')} {rp(nf)}</span>
          {d.foreign?.range && <span className="muted"> · {d.foreign.range}</span>}
        </dd></div>}
      </dl>
      {recent.length > 0 && (
        <>
          <h3 className="label">{t('flow_insider')}</h3>
          <ul className="plain">{recent.map((m, i) => (
            <li key={i}><span className="muted">{m.date}</span> {m.name} · <span className={m.side > 0 ? 'delta-up' : m.side < 0 ? 'delta-down' : ''}>{m.side > 0 ? t('flow_buy') : m.side < 0 ? t('flow_sell') : m.action}</span>
              {m.change_pct != null && ` (${m.change_pct > 0 ? '+' : ''}${num(m.change_pct, 2)}%)`}
              {m.now_pct != null && <span className="muted"> → {num(m.now_pct, 2)}%</span>}</li>))}
          </ul>
        </>
      )}
      {(d.stream ?? []).length > 0 && (
        <details className="why">
          <summary>{t('flow_stream')}</summary>
          <ul className="plain">{(d.stream ?? []).slice(0, 5).map((p, i) => (
            <li key={i}>{p.text} <span className="muted small">· {p.likes} ♥</span></li>))}
          </ul>
          <p className="note">{t('flow_stream_note')}</p>
        </details>
      )}
      <p className="note">{l({id: 'Sumber: terminal Stockbit Anda.', en: 'Source: your Stockbit terminal.'})}</p>
    </section>
  );
}

export function LivePanel({k, decimals: fallback, klass}: {k: string; decimals: number; klass: string}) {
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
          {data.realtime ? t('live_rt', {src: data.source === 'stockbit' ? 'Stockbit' : 'Binance'})
            : data.source === 'daily' ? t('live_daily') : t('live_delay', {m: data.delay_min ?? 15})}
        </span>
      </div>
      <p className="live-price">
        <span className="price big">{money(data.last, decimals, data.unit)}</span>
        {data.chg_pct != null && <span className={`delta ${goodForOwner ? 'delta-up' : 'delta-down'}`}>{pct(data.chg_pct, 2)} <span className="muted">{t('today')}</span></span>}
        <span className="muted small">{t('updated')} {when(data.at)}</span>
      </p>
      {data.note && <p className="note">{l(data.note)}</p>}
      {data.bars.length > 1 ? <LiveChart bars={data.bars} decimals={decimals} label={t('live_h')} area /> : <p className="note">{t('live_closed')}</p>}
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

type Range = '1d' | '1m' | '3m' | '1y' | '5y';
export function HistoryPanel({k, range, klass, onAuth}: {k: string; range: Exclude<Range, '1d'>; klass: string; onAuth: () => void}) {
  const {t, money, pct} = useT();
  const h = useLoad(() => api.history(k, range), [k, range], onAuth);
  return (
    <Async state={h}>
      {d => {
        if (d.bars.length < 2) return <p className="note">{t('hist_none')}</p>;
        const first = d.bars[0].c, last = d.bars[d.bars.length - 1].c;
        const chg = (last / first - 1) * 100;
        const good = chg >= 0 ? klass !== 'fx' : klass === 'fx';
        return (
          <section className="live">
            <p className="live-price">
              <span className="price big">{money(last, d.decimals, d.unit)}</span>
              <span className={`delta ${good ? 'delta-up' : 'delta-down'}`}>{pct(chg, 2)} <span className="muted">{t(`rng_${range}`)}</span></span>
            </p>
            <LiveChart bars={d.bars} decimals={d.decimals} label={t('chart_hist')} area={range !== '1m'} />
          </section>
        );
      }}
    </Async>
  );
}

/** Today's live chart or a longer daily chart, switched by one row of range chips. */
export function TickerNews({k, onAuth}: {k: string; onAuth: () => void}) {
  const {t} = useT();
  const f = useLoad(() => api.tickerFeed(k), [k], onAuth);
  return (
    <Async state={f}>
      {d => (
        <>
          <StoryList items={d.items} empty={t('no_ticker_news')} />
          {d.posts.length > 0 && (
            <>
              <h3 className="label">{t('flow_stream')}</h3>
              <ul className="plain">{d.posts.slice(0, 6).map((p, i) => (
                <li key={i}>{p.text} <span className="muted small">· {p.likes} ♥</span></li>))}
              </ul>
              <p className="note">{t('flow_stream_note')}</p>
            </>
          )}
        </>
      )}
    </Async>
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
  const {t, num, when, lang} = useT();
  const status = useLoad(api.status, [], onAuth);
  const prefs = useLoad(api.settings, [], onAuth);
  const [levels, setLevels] = useState('');
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (prefs.data) setLevels((prefs.data.levels.USDIDR ?? []).join(', ')); }, [prefs.data]);
  const parse = (s: string) => Number(s.replace(/\s/g, '').replace(lang === 'id' ? /\./g : /,/g, '').replace(',', '.'));
  const saveLevels = async () => {
    const vals = levels.split(/[,;]\s*|\s+/).map(parse).filter(v => v > 0);
    await api.saveSettings({levels: {...(prefs.data?.levels ?? {}), USDIDR: vals}});
    setSaved(true); prefs.reload();
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

      <h2 className="section-h">{t('more')}</h2>
      <ul className="plain">
        <li><a href="#/peringatan">{t('nav_alerts')}</a></li>
        <li><a href="#/rekam">{t('nav_track')}</a></li>
      </ul>

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
          <img className="login-logo" src="/arah-logo.png" alt="ARAH by LRM Corporation" width={280} height={122} />
          <p className="note">{t('login_title')}</p>
        </header>
        <TextInput type="password" label={t('password')} value={pw} onChange={setPw} autoComplete="current-password" hasAutoFocus
          status={err ? {type: 'error', message: err} : undefined} width="100%" />
        <Button type="submit" variant="primary" label={t('login')} isLoading={busy} width="100%" size="lg" />
      </form>
    </main>
  );
}
