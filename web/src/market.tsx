import {useMemo, useState} from 'react';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {TextInput} from '@astryxdesign/core/TextInput';
import {api, type MarketRow} from './api';
import {Spark} from './charts';
import {Async, ChipBar, VerdictTag, VigilanceLine} from './components';
import {useLoad} from './hooks';
import {useT, type Key} from './i18n';
import {CalcPage, RecsPanel} from './pages';

interface Props {onAuth: () => void; seg: string}

// Segments in the order a newcomer asks: what to buy, Indonesian stocks, US stocks, the indices,
// currencies, commodities, then the exchange calculator.
export const SEGMENTS: {key: string; label: Key; group?: string}[] = [
  {key: 'pilihan', label: 'seg_picks'},
  {key: 'saham-id', label: 'tab_id', group: 'stock_id'},
  {key: 'saham-as', label: 'tab_us', group: 'stock_us'},
  {key: 'indeks', label: 'indices', group: 'index'},
  {key: 'kurs', label: 'nav_fx', group: 'fx'},
  {key: 'komoditas', label: 'tab_comm', group: 'commodity'},
  {key: 'hitung', label: 'nav_calc'},
];

function Row({r}: {r: MarketRow}) {
  const {nm, money, pct, t} = useT();
  const fx = r.klass === 'fx';
  // Colour on the daily change means good or bad for the owner: a rising rupiah rate is bad news.
  const good = (r.chg1d ?? 0) >= 0 ? !fx : fx;
  return (
    <li>
      <a className="qrow" href={`#/a/${encodeURIComponent(r.key)}`}>
        <span className="qrow-name">
          <strong>{r.klass === 'stock' ? r.key : nm(r)}</strong>
          <span className="muted small">{r.klass === 'stock' ? r.name : r.name !== r.key ? r.key : ''}</span>
        </span>
        <Spark values={r.spark} label={`${nm(r)}: ${t('chart_hist')}`} />
        <span className="qrow-px">
          <span className="price">{money(r.price, r.decimals, r.unit)}</span>
          {r.chg1d != null && <span className={`small ${Math.abs(r.chg1d) < 0.05 ? 'muted' : good ? 'delta-up' : 'delta-down'}`}>{pct(r.chg1d, 2)}</span>}
        </span>
        {r.verdict && <span className="qrow-v"><VerdictTag v={r.verdict} /></span>}
      </a>
    </li>
  );
}

function Quotes({onAuth, group}: {onAuth: () => void; group: string}) {
  const {t, l} = useT();
  const [q, setQ] = useState('');
  const rows = useLoad(() => api.markets(group, '1w'), [group], onAuth);
  const usd = useLoad(() => (group === 'fx' ? api.asset('USDIDR', '1w') : Promise.resolve(null)), [group], onAuth);
  const stocks = group.startsWith('stock');
  return (
    <>
      {group === 'fx' && usd.data?.vigilance && (
        <VigilanceLine v={usd.data.vigilance} decimals={0} horizonName={l(usd.data.horizon_name)} />
      )}
      {stocks && (
        <div className="search">
          <TextInput label={t('search_stock')} value={q} onChange={setQ} width="100%" placeholder={group === 'stock_id' ? 'BBCA, Telkom' : 'NVDA, Apple'} />
        </div>
      )}
      <Async state={rows}>
        {d => {
          const needle = q.trim().toLowerCase();
          let list = d.rows.filter(r => !needle || r.key.toLowerCase().includes(needle) || r.name.toLowerCase().includes(needle));
          // Stocks: best verdict first, so the list answers "which ones are worth a look".
          if (stocks) list = [...list].sort((a, b) => (b.verdict?.score ?? -1) - (a.verdict?.score ?? -1));
          if (d.rows.length === 0) return <EmptyState isCompact title={t('recs_wait_title')} description={t('recs_wait_desc')} />;
          if (list.length === 0) return <p className="note">{t('no_match')}</p>;
          return (
            <>
              {stocks && <p className="note">{t('verdict_list_note')}</p>}
              <ul className="qlist">{list.map(r => <Row key={r.key} r={r} />)}</ul>
            </>
          );
        }}
      </Async>
    </>
  );
}

export function MarketPage({onAuth, seg}: Props) {
  const {t} = useT();
  const current = SEGMENTS.find(s => s.key === seg) ?? SEGMENTS[0];
  const items = useMemo(() => SEGMENTS.map(s => ({key: s.key, text: t(s.label)})), [t]);
  return (
    <>
      <header className="page-head"><h1 className="page-title">{t('nav_market')}</h1></header>
      <ChipBar items={items} value={current.key} label={t('market')} onChange={k => { window.location.hash = `/pasar/${k}`; }} />
      <div className="seg-body">
        {current.key === 'pilihan' ? <RecsPanel onAuth={onAuth} />
          : current.key === 'hitung' ? <CalcPage onAuth={onAuth} embedded />
          : <Quotes key={current.group} onAuth={onAuth} group={current.group!} />}
      </div>
    </>
  );
}
