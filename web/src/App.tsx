import {useEffect, useState} from 'react';
import {Theme} from '@astryxdesign/core/theme';
import {neutralTheme} from '@astryxdesign/theme-neutral/built';
import {api, type Lang} from './api';
import {Lines} from './components';
import {useHashRoute, useLoad} from './hooks';
import {LangCtx, useT, type Key} from './i18n';
import {AssetPage, CalcPage, Login, Markets, SettingsPage, Today, TrackPage, World} from './pages';

const NAV: {to: string; key: Key}[] = [
  {to: '/', key: 'nav_today'}, {to: '/hitung', key: 'nav_calc'}, {to: '/saham', key: 'nav_stocks'}, {to: '/dunia', key: 'nav_world'}, {to: '/atur', key: 'nav_settings'},
];
// Reference pages: reachable from the footer so the main row stays at four items.
const MORE: {to: string; key: Key}[] = [{to: '/kurs', key: 'nav_fx'}, {to: '/rekam', key: 'nav_track'}];
type Mode = 'system' | 'light' | 'dark';

function readMode(): Mode {
  try {
    const m = localStorage.getItem('arah-theme');
    return m === 'light' || m === 'dark' ? m : 'system';
  } catch { return 'system'; }
}

function Shell({route, children}: {route: string; children: React.ReactNode}) {
  const {t} = useT();
  const current = route.startsWith('/a/') ? '' : route;
  return (
    <>
      <a className="skip" href="#main">{t('nav_today')}</a>
      <header className="top">
        <div className="top-in">
          <a className="brand" href="#/" aria-label="ARAH by LRM">
            <span className="lrm-mark icon" aria-hidden="true" /> ARAH <span className="brand-by">by LRM</span>
          </a>
          <nav aria-label={t('main_nav')}>
            <ul>{NAV.map(n => (
              <li key={n.to}><a href={`#${n.to}`} aria-current={current === n.to ? 'page' : undefined}>{t(n.key)}</a></li>))}
            </ul>
          </nav>
        </div>
      </header>
      <main id="main" className="page">{children}</main>
      <footer className="foot">
        <nav aria-label={t('more')}>
          <ul>{MORE.map(n => <li key={n.to}><a href={`#${n.to}`}>{t(n.key)}</a></li>)}</ul>
        </nav>
        <p>{t('disclaimer')}</p>
      </footer>
    </>
  );
}

export default function App() {
  const [route] = useHashRoute();
  const session = useLoad(api.session, []);
  const [lang, setLang] = useState<Lang>('id');
  const [mode, setMode] = useState<Mode>(readMode);
  useEffect(() => { if (session.data) setLang(session.data.lang); }, [session.data]);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const changeLang = (l: Lang) => { setLang(l); void api.saveSettings({lang: l}); };
  const changeMode = (m: string) => {
    const next = (m === 'light' || m === 'dark' ? m : 'system') as Mode;
    setMode(next);
    try { localStorage.setItem('arah-theme', next); } catch { /* storage unavailable */ }
  };
  const onAuth = session.reload;

  let body: React.ReactNode;
  if (!session.data) {
    body = <main className="page"><Lines n={6} /></main>;
  } else if (session.data.auth_required && !session.data.authed) {
    body = <Login onDone={session.reload} />;
  } else {
    const p = {onAuth};
    const page = route === '/' ? <Today {...p} />
      : route === '/kurs' ? <Markets {...p} kind="fx" key="fx" />
      : route === '/hitung' ? <CalcPage {...p} />
      : route === '/saham' ? <Markets {...p} kind="stocks" key="stocks" />
      : route === '/dunia' ? <World {...p} />
      : route === '/rekam' ? <TrackPage {...p} />
      : route === '/atur' ? <SettingsPage {...p} onLang={changeLang} themeMode={mode} onTheme={changeMode} authRequired={session.data.auth_required} />
      : route.startsWith('/a/') ? <AssetPage {...p} k={decodeURIComponent(route.slice(3))} key={route} />
      : <Today {...p} />;
    body = <Shell route={route}>{page}</Shell>;
  }
  return (
    <Theme theme={neutralTheme} mode={mode}>
      <LangCtx.Provider value={lang}>{body}</LangCtx.Provider>
    </Theme>
  );
}
