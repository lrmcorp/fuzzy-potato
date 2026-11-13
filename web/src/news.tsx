import {useMemo, useState} from 'react';
import {EmptyState} from '@astryxdesign/core/EmptyState';
import {api, type Story} from './api';
import {Async, ChipBar} from './components';
import {useLoad} from './hooks';
import {useT, type Key} from './i18n';

const SCOPES: {key: string; label: Key}[] = [
  {key: 'ID', label: 'c_ID'}, {key: 'US', label: 'c_US'}, {key: 'ASIA', label: 'scope_asia'}, {key: 'GLOBAL', label: 'c_GLOBAL'},
];
// What each feed topic means to a reader, in their words.
const TOPIC: Record<string, Key> = {
  id_market: 'tp_market', id_flow: 'tp_flow', id_insider: 'tp_insider', id_politics: 'tp_policy', id_commodity: 'tp_commodity',
  us_market: 'tp_market', us_official: 'tp_central', us_insider: 'tp_insider_us', us_politics: 'tp_policy',
  jp: 'c_JP', sg: 'c_SG', cn: 'c_CN', global: 'tp_global',
};

export function StoryList({items, empty}: {items: Story[]; empty: string}) {
  const {t, when} = useT();
  if (items.length === 0) return <p className="note">{empty}</p>;
  return (
    <ol className="stories">
      {items.map(s => (
        <li key={s.id}>
          <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title}</a>
          <span className="story-meta">
            {s.outlets > 1 && <span className="story-n">{t('outlets', {n: s.outlets})}</span>}
            <span>{s.source || t('src_unknown')}</span>
            <span>{when(s.published_at)}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

export function NewsPage({onAuth, scope: first}: {onAuth: () => void; scope?: string}) {
  const {t, l} = useT();
  const [scope, setScope] = useState(first && ['ID', 'US', 'ASIA', 'GLOBAL'].includes(first) ? first : 'ID');
  const [topic, setTopic] = useState('');
  const feed = useLoad(() => api.feed(scope, topic || undefined), [scope, topic], onAuth);
  const scopes = useMemo(() => SCOPES.map(s => ({key: s.key, text: t(s.label)})), [t]);
  return (
    <>
      <header className="page-head">
        <h1 className="page-title">{t('nav_news')}</h1>
        <p className="lead">{t('news_lead')}</p>
      </header>
      <ChipBar items={scopes} value={scope} label={t('region')} onChange={k => { setScope(k); setTopic(''); }} />
      <Async state={feed}>
        {d => (
          <>
            {d.topics.length > 1 && (
              <ChipBar label={t('topic')} value={topic}
                items={[{key: '', text: t('tp_all')}, ...d.topics.filter(x => TOPIC[x]).map(x => ({key: x, text: t(TOPIC[x])}))]}
                onChange={setTopic} />
            )}
            {!topic && d.desks.map(dk => (
              <section key={dk.country} className="desk">
                <h2 className="label">{t('desk_says', {c: t(`c_${dk.country}` as Key)})}</h2>
                <p className="verdict">{l(dk.summary)}</p>
                {dk.events.slice(0, 3).map((e, i) => (
                  <p key={i} className="desk-ev"><strong>{l(e.what)}</strong> {l(e.effect)}</p>
                ))}
              </section>
            ))}
            {d.items.length === 0 && !d.desks.length
              ? <EmptyState isCompact title={t('no_news')} description={t('no_news_desc')} />
              : <StoryList items={d.items} empty={t('no_news')} />}
            <p className="note">{t('news_rank_note')}</p>
          </>
        )}
      </Async>
    </>
  );
}
