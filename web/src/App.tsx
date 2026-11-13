import {useEffect, useState} from 'react';
import {Theme} from '@astryxdesign/core/theme';
import {neutralTheme} from '@astryxdesign/theme-neutral/built';
import {api, type Lang} from './api';
import {Lines} from './components';
import {useHashRoute, useLoad} from './hooks';
import {LangCtx, useT, type Key} from './i18n';
import {AlertsPage} from './alerts';
import {MarketPage} from './market';
import {NewsPage} from './news';
import {AssetPage, Login, SettingsPage, Today, TrackPage} from './pages';

// Five destinations, in the order a newcomer uses them. On a phone they sit in a bar at the bottom,
// within thumb reach; on a wide screen the same five sit in a rail on the left.
const NAV: {to: string; key: Key; match: (r: string) => boolean}[] = [
  {to: '/', key: 'nav_today', match: r => r === '/'},
  {to: '/pasar', key: 'nav_market', match: r => r.startsWith('/pasar') || r.startsWith('/a/')},
  {to: '/berita', key: 'nav_news', match: r => r.startsWith('/berita')},
  {to: '/peringatan', key: 'nav_alerts', match: r => r.startsWith('/peringatan')},
  {to: '/atur', key: 'nav_settings', match: r => r.startsWith('/atur') || r.startsWith('/rekam')},
];

// Old addresses keep working: bookmarks and Telegram links point at them.
const MOVED: Record<string, string> = {'/saham': '/pasar/saham-id', '/kurs': '/pasar/kurs', '/hitung': '/pasar/hitung', '/dunia': '/berita'};

function Shell({route, children}: {route: string; children: React.ReactNode}) {
  const {t} = useT();
  const links = NAV.map(n => {
    const on = n.match(route);
    return <li key={n.to}><a href={`#${n.to}`} aria-current={on ? 'page' : undefined}>{t(n.key)}</a></li>;
  });
  return (
    <div className="app">
      <a className="skip" href="#main">{t('skip')}</a>
      <header className="top">
        <a className="brand" href="#/" aria-label="ARAH by LRM">
          <span className="lrm-mark icon" aria-hidden="true" /> ARAH <span className="brand-by">by LRM</span>
        </a>
      </header>
      <nav className="tabs" aria-label={t('main_nav')}><ul>{links}</ul></nav>
      <main id="main" className="page">{children}
        <footer className="foot"><p>{t('disclaimer')}</p></footer>
      </main>
    </div>
  );
}

export default function App() {
  const [route] = useHashRoute();
  const session = useLoad(api.session, []);
  const [lang, setLang] = useState<Lang>('id');
  useEffect(() => { if (session.data) setLang(session.data.lang); }, [session.data]);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const changeLang = (l: Lang) => { setLang(l); void api.saveSettings({lang: l}); };
  const onAuth = session.reload;

  let body: React.ReactNode;
  if (!session.data) {
    body = <main className="page"><Lines n={6} /></main>;
  } else if (session.data.auth_required && !session.data.authed) {
    body = <Login onDone={session.reload} />;
  } else {
    const p = {onAuth};
    const r = MOVED[route] ?? route;
    const page = r === '/' ? <Today {...p} />
      : r.startsWith('/pasar') ? <MarketPage {...p} seg={r.split('/')[2] ?? 'pilihan'} />
      : r === '/berita' ? <NewsPage {...p} />
      : r === '/peringatan' ? <AlertsPage {...p} />
      : r === '/rekam' ? <TrackPage {...p} />
      : r === '/atur' ? <SettingsPage {...p} onLang={changeLang} authRequired={session.data.auth_required} />
      : r.startsWith('/a/') ? <AssetPage {...p} k={decodeURIComponent(r.slice(3))} key={r} />
      : <Today {...p} />;
    body = <Shell route={r}>{page}</Shell>;
  }
  return (
    <Theme theme={neutralTheme} mode="light">
      <LangCtx.Provider value={lang}>{body}</LangCtx.Provider>
    </Theme>
  );
}
