import {useCallback, useEffect, useRef, useState} from 'react';
import {Theme} from '@astryxdesign/core/theme';
import {neutralTheme} from '@astryxdesign/theme-neutral/built';
import {AlertSheetHost} from './alertsheet';
import {AlertsPage} from './alerts';
import {api, type Lang, type PulseInfo} from './api';
import {AssetView} from './asset';
import {CariPage, SearchPanel} from './cari';
import {HomePage} from './home';
import {useHashRoute, useLoad} from './hooks';
import {LangCtx} from './i18n';
import {MarketPage} from './market';
import {NewsPage} from './news';
import {Login, SettingsPage, TrackPage} from './pages';
import {Icon, Skeleton, StaleChip, ToastHost} from './ui';

// Desktop: Ringkasan · Pasar · Berita · Peringatan · Atur. Phone: Ringkasan · Pasar · Cari · Peringatan · Atur
// (Berita is reached from the home "Kenapa?" link and the asset tab).
const DESK = [
  {to: '/', label: 'Ringkasan', match: (r: string) => r === '/'},
  {to: '/pasar', label: 'Pasar', match: (r: string) => r.startsWith('/pasar') || r.startsWith('/a/')},
  {to: '/berita', label: 'Berita', match: (r: string) => r.startsWith('/berita')},
  {to: '/peringatan', label: 'Peringatan', match: (r: string) => r.startsWith('/peringatan')},
  {to: '/atur', label: 'Atur', match: (r: string) => r.startsWith('/atur') || r.startsWith('/rekam')},
];
const PHONE = [
  {to: '/', label: 'Ringkasan', icon: 'home', match: (r: string) => r === '/'},
  {to: '/pasar', label: 'Pasar', icon: 'market', match: (r: string) => r.startsWith('/pasar')},
  {to: '/cari', label: 'Cari', icon: 'search', match: (r: string) => r.startsWith('/cari')},
  {to: '/peringatan', label: 'Peringatan', icon: 'bell', match: (r: string) => r.startsWith('/peringatan')},
  {to: '/atur', label: 'Atur', icon: 'settings', match: (r: string) => r.startsWith('/atur') || r.startsWith('/rekam')},
];
// Old addresses keep working: bookmarks and Telegram links point at them.
const MOVED: Record<string, string> = {'/saham': '/pasar/saham', '/kurs': '/pasar/kurs', '/hitung': '/pasar', '/dunia': '/berita'};

function Logo() {
  return (
    <a className="logo" href="#/" aria-label="ARAH by LRM Corporation, ke Ringkasan">
      <img src="/arah-logo.png" alt="" width={110} height={48} />
    </a>
  );
}

/** The header search: type to see tickers and "Tanya ARAH"; the / key focuses it from anywhere. */
function HeaderSearch() {
  const [q, setQ] = useState('');
  const [open, setOpen] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === '/' && tag !== 'INPUT' && tag !== 'TEXTAREA') { e.preventDefault(); input.current?.focus(); setOpen(true); }
      if (e.key === 'Escape') setOpen(false);
    };
    const onClick = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onClick);
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onClick); };
  }, []);
  useEffect(() => {
    const close = () => setOpen(false);
    window.addEventListener('hashchange', close);
    return () => window.removeEventListener('hashchange', close);
  }, []);
  return (
    <div className="hsearch" ref={box}>
      <label>
        <Icon name="search" size={18} />
        <input ref={input} type="search" placeholder="Cari saham atau tanya ARAH" aria-label="Cari saham atau tanya ARAH"
          value={q} onChange={e => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} />
        <kbd aria-hidden="true">/</kbd>
      </label>
      {open && <div className="hsearch-drop"><SearchPanel q={q} onPick={() => setOpen(false)} /></div>}
    </div>
  );
}

function Shell({route, pulse, reloadPulse, children}: {route: string; pulse: PulseInfo | null; reloadPulse: () => void; children: React.ReactNode}) {
  const asset = route.startsWith('/a/');
  return (
    <div className={`shell${asset ? ' has-actionbar' : ''}`}>
      <a className="sr-only" href="#main">Lompat ke isi</a>
      <header className="hdr">
        <div className="hdr-in">
          <Logo />
          <nav className="nav" aria-label="Menu utama">
            {DESK.map(n => (
              <a key={n.to} href={`#${n.to}`} aria-current={n.match(route) ? 'page' : undefined}>
                {n.label}{n.to === '/peringatan' && pulse?.alerts_active ? <span className="badge">{pulse.alerts_active} aktif</span> : null}
              </a>
            ))}
          </nav>
          <HeaderSearch />
          <SessionChip pulse={pulse} />
          <StaleChip pulse={pulse} onChanged={reloadPulse} wide={asset} />
        </div>
      </header>
      {!asset && (
        <div className="phone-top">
          <Logo />
          <span className="phone-chips"><SessionChip pulse={pulse} /><StaleChip pulse={pulse} onChanged={reloadPulse} /></span>
        </div>
      )}
      <main id="main" className="main">{children}</main>
      <footer className="foot">ARAH (AI Research &amp; Analysis Hub) by LRM Corporation - Internal Use Only</footer>
      <nav className="tabbar" aria-label="Menu utama">
        {PHONE.map(n => (
          <a key={n.to} href={`#${n.to}`} aria-current={n.match(route) ? 'page' : undefined}>
            <Icon name={n.icon} size={24} />{n.label}
          </a>
        ))}
      </nav>
    </div>
  );
}

/** IDX session from the exchange's timetable in WIB: Pra-pembukaan, Sesi 1, Istirahat, Sesi 2 or Tutup. */
function SessionChip({pulse}: {pulse: PulseInfo | null}) {
  const s = pulse?.idx;
  if (!s) return null;
  return <span className={`sess${s.open ? ' sess-open' : ''}`} aria-label={`Bursa Efek Indonesia: ${s.label}`}><span className="sess-dot" />BEI · {s.label}</span>;
}

function usePulse(enabled: boolean): [PulseInfo | null, () => void] {
  const [p, setP] = useState<PulseInfo | null>(null);
  const load = useCallback(() => { if (enabled) api.pulse().then(setP).catch(() => undefined); }, [enabled]);
  useEffect(() => {
    load();
    const id = window.setInterval(load, 60000);
    return () => window.clearInterval(id);
  }, [load]);
  return [p, load];
}

export default function App() {
  const [route] = useHashRoute();
  const session = useLoad(api.session, []);
  const [lang, setLang] = useState<Lang>('id');
  useEffect(() => { if (session.data) setLang(session.data.lang); }, [session.data]);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const authed = !!session.data && (!session.data.auth_required || session.data.authed);
  const [pulse, reloadPulse] = usePulse(authed);

  const changeLang = (l: Lang) => { setLang(l); void api.saveSettings({lang: l}); };
  const onAuth = session.reload;

  let body: React.ReactNode;
  if (!session.data) {
    body = <main className="main"><Skeleton lines={6} /></main>;
  } else if (!authed) {
    body = <Login onDone={session.reload} />;
  } else {
    const p = {onAuth};
    const r = MOVED[route] ?? route;
    const paused = pulse?.state === 'paused';
    const page = r === '/' ? <HomePage {...p} pulse={pulse} />
      : r.startsWith('/pasar') ? <MarketPage {...p} seg={r.split('/')[2] ?? 'pilihan'} paused={paused} />
      : r === '/cari' ? <CariPage />
      : r.startsWith('/berita') ? <NewsPage {...p} scope={r.split('/')[2]} key={r} />
      : r === '/peringatan' ? <AlertsPage {...p} onChanged={reloadPulse} />
      : r === '/rekam' ? <TrackPage {...p} />
      : r === '/atur' ? <SettingsPage {...p} onLang={changeLang} authRequired={session.data.auth_required} />
      : r.startsWith('/a/') ? <AssetView {...p} k={decodeURIComponent(r.slice(3))} key={r} pulse={pulse} onPulse={reloadPulse} />
      : <HomePage {...p} pulse={pulse} />;
    body = (
      <>
        <Shell route={r} pulse={pulse} reloadPulse={reloadPulse}>{page}</Shell>
        <AlertSheetHost onChanged={reloadPulse} telegram={!!pulse?.telegram} />
        <ToastHost />
      </>
    );
  }
  return (
    <Theme theme={neutralTheme} mode="light">
      <LangCtx.Provider value={lang}>{body}</LangCtx.Provider>
    </Theme>
  );
}
