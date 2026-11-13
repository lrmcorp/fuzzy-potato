import {useEffect, useState} from 'react';
import {Badge} from '@astryxdesign/core/Badge';
import {Banner} from '@astryxdesign/core/Banner';
import {Button} from '@astryxdesign/core/Button';
import {Selector} from '@astryxdesign/core/Selector';
import {TextInput} from '@astryxdesign/core/TextInput';
import {api} from './api';
import {Async} from './components';
import {useLoad} from './hooks';
import {useT} from './i18n';

type PushState = 'checking' | 'unsupported' | 'ios-home' | 'denied' | 'off' | 'on';

function keyBytes(b64: string): Uint8Array {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, c => c.charCodeAt(0));
}

const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || (navigator as {standalone?: boolean}).standalone === true;

async function registration() {
  return navigator.serviceWorker.register('/sw.js');
}

/** Turns phone notifications on or off for this device, explaining the one extra step iPhones need. */
function PushCard() {
  const {t} = useT();
  const [state, setState] = useState<PushState>('checking');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
        setState(isIos() && !standalone() ? 'ios-home' : 'unsupported');
        return;
      }
      if (Notification.permission === 'denied') { setState('denied'); return; }
      const reg = await registration();
      setState((await reg.pushManager.getSubscription()) ? 'on' : 'off');
    })().catch(() => setState('unsupported'));
  }, []);

  const enable = async () => {
    setBusy(true); setMsg(null);
    try {
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') { setState(perm === 'denied' ? 'denied' : 'off'); return; }
      const reg = await registration();
      const {key} = await api.pushInfo();
      const sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: keyBytes(key) as BufferSource});
      await api.pushSubscribe(sub.toJSON());
      setState('on'); setMsg(t('push_on_msg'));
    } catch {
      setMsg(t('push_fail'));
    } finally { setBusy(false); }
  };
  const disable = async () => {
    setBusy(true); setMsg(null);
    try {
      const sub = await (await registration()).pushManager.getSubscription();
      if (sub) { await api.pushUnsubscribe(sub.endpoint); await sub.unsubscribe(); }
      setState('off');
    } finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setMsg(null);
    try { const r = await api.pushTest(); setMsg(r.sent ? t('push_test_sent') : t('push_fail')); }
    catch { setMsg(t('push_wait')); }
    finally { setBusy(false); }
  };

  return (
    <section className="panel" aria-labelledby="push-h">
      <h2 id="push-h" className="panel-h">{t('push_h')}</h2>
      {state === 'checking' && <p className="note">{t('loading')}</p>}
      {state === 'on' && (
        <>
          <p><Badge variant="success" label={t('push_is_on')} /> {t('push_on_desc')}</p>
          <div className="actions">
            <Button label={t('push_test')} onClick={test} isLoading={busy} />
            <Button label={t('push_disable')} variant="ghost" onClick={disable} />
          </div>
        </>
      )}
      {state === 'off' && (
        <>
          <p>{t('push_off_desc')}</p>
          <div className="actions"><Button label={t('push_enable')} variant="primary" onClick={enable} isLoading={busy} /></div>
        </>
      )}
      {state === 'ios-home' && <p>{t('push_ios')}</p>}
      {state === 'denied' && <p>{t('push_denied')}</p>}
      {state === 'unsupported' && <p>{t('push_unsupported')}</p>}
      {msg && <p className="note" role="status">{msg}</p>}
    </section>
  );
}

export function AlertsPage({onAuth}: {onAuth: () => void}) {
  const {t, money, when, lang} = useT();
  const prefs = useLoad(api.settings, [], onAuth);
  const alerts = useLoad(api.alerts, [], onAuth);
  const [aKey, setAKey] = useState('USDIDR');
  const [aOp, setAOp] = useState('>');
  const [aLevel, setALevel] = useState('');
  const [err, setErr] = useState<string | null>(null);
  // Numbers are typed the way they are shown: 18,500 or 18500 (commas are thousands).
  const parse = (s: string) => Number(s.replace(/[\s,]/g, '').replace(/^rp/i, ''));
  const add = async (key = aKey, op = aOp, raw = aLevel) => {
    const v = parse(raw);
    if (!(v > 0)) { setErr(t('level_bad')); return; }
    setErr(null);
    await api.addAlert(key, op, v); setALevel(''); alerts.reload();
  };
  const presets = [18000, 18500, 19000];
  return (
    <>
      <header className="page-head">
        <h1 className="page-title">{t('nav_alerts')}</h1>
        <p className="lead">{t('alerts_lead')}</p>
      </header>
      <PushCard />

      <section className="panel" aria-labelledby="new-h">
        <h2 id="new-h" className="panel-h">{t('alert_new')}</h2>
        <p className="note">{t('alert_quick')}</p>
        <div className="actions wrap">
          {presets.map(p => (
            <Button key={p} label={`USD/IDR > ${money(p, 0, 'Rp')}`} onClick={() => add('USDIDR', '>', String(p))} />
          ))}
        </div>
        <div className="form-grid">
          <Selector label={t('asset')} value={aKey} onChange={setAKey} hasSearch width="100%"
            options={(prefs.data?.assets ?? []).map(a => ({value: a.key, label: a.name.replace('/', '') === a.key || a.name === a.key ? a.name : `${a.key} ${a.name}`}))} />
          <Selector label={t('when')} value={aOp} onChange={setAOp} width="100%"
            options={[{value: '>', label: t('goes_above')}, {value: '<', label: t('goes_below')}]} />
          <TextInput label={t('level')} value={aLevel} onChange={setALevel} onEnter={() => void add()} width="100%" inputMode="decimal"
            placeholder={lang === 'id' ? '18,500' : '18,500'} status={err ? {type: 'error', message: err} : undefined} />
          <Button label={t('add_alert')} variant="primary" onClick={() => void add()} width="100%" />
        </div>
      </section>

      <section aria-labelledby="list-h">
        <h2 id="list-h" className="section-h">{t('alerts')}</h2>
        <Async state={alerts}>
          {d => {
            const open = d.items.filter(a => !a.triggered_at);
            const done = d.items.filter(a => a.triggered_at).sort((a, b) => (b.triggered_at ?? 0) - (a.triggered_at ?? 0));
            if (d.items.length === 0) return <p className="note">{t('no_alerts')}</p>;
            return (
              <>
                <ul className="alist">{open.map(a => (
                  <li key={a.id}>
                    <span><strong>{a.name}</strong> {a.op === '>' ? t('goes_above') : t('goes_below')} {money(a.level, a.decimals, a.unit)}</span>
                    <Button label={t('remove')} size="sm" variant="ghost" onClick={async () => { await api.delAlert(a.id); alerts.reload(); }} />
                  </li>))}
                </ul>
                {done.length > 0 && (
                  <>
                    <h3 className="label">{t('alerts_done')}</h3>
                    <ul className="alist done">{done.slice(0, 10).map(a => (
                      <li key={a.id}>
                        <span>{a.name} {a.op === '>' ? t('goes_above') : t('goes_below')} {money(a.level, a.decimals, a.unit)}
                          <span className="muted small"> · {when(a.triggered_at)}{a.last_price ? ` · ${money(a.last_price, a.decimals, a.unit)}` : ''}</span></span>
                        <Button label={t('remove')} size="sm" variant="ghost" onClick={async () => { await api.delAlert(a.id); alerts.reload(); }} />
                      </li>))}
                    </ul>
                  </>
                )}
              </>
            );
          }}
        </Async>
      </section>
      {prefs.error && <Banner status="warning" title={t('load_fail')} />}
    </>
  );
}
