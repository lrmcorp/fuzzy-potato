/* Peringatan (redesign pack prompt 05): alerts grouped by asset, phone notifications for this device. */
import {useEffect, useState} from 'react';
import {api, type AlertItem} from './api';
import {useLoad} from './hooks';
import {useT} from './i18n';
import {disablePush, enablePush, pushState, type PushState} from './push';
import {Icon, Skeleton, toast} from './ui';

/** Which kinds of notification come, one switch each, plus the quiet hours. */
function PushKinds() {
  const p = useLoad(api.pushPrefs, []);
  const [prefs, setPrefs] = useState<Record<string, boolean> | null>(null);
  useEffect(() => { if (p.data) setPrefs(p.data.prefs); }, [p.data]);
  if (!p.data || !prefs) return <Skeleton lines={3} />;
  const flip = async (k: string) => {
    const next = {...prefs, [k]: !prefs[k]};
    setPrefs(next);
    try { setPrefs((await api.setPushPrefs({[k]: next[k]})).prefs); } catch { setPrefs(prefs); toast({text: 'Belum tersimpan. Coba lagi.'}); }
  };
  return (
    <div className="push-kinds">
      <h3 className="hero-sub">Kirim notifikasi untuk</h3>
      <ul>
        {p.data.kinds.map(k => (
          <li key={k.key}>
            <label className="switch-row">
              <span><b>{k.title}</b><span className="caption">{k.text}</span></span>
              <input type="checkbox" role="switch" checked={!!prefs[k.key]} onChange={() => flip(k.key)} />
            </label>
          </li>
        ))}
        <li>
          <label className="switch-row">
            <span><b>Jam tenang 21.00 sampai 06.00</b><span className="caption">Ringkasan pasar, agenda, dan info koneksi ditahan. Peringatan harga dan Pilihan tetap masuk.</span></span>
            <input type="checkbox" role="switch" checked={!!prefs.quiet} onChange={() => flip('quiet')} />
          </label>
        </li>
      </ul>
    </div>
  );
}

function PushCard() {
  const [state, setState] = useState<PushState>('checking');
  const [busy, setBusy] = useState(false);
  useEffect(() => { void pushState().then(setState); }, []);
  const run = async (fn: () => Promise<PushState>) => {
    setBusy(true);
    try { setState(await fn()); } catch { toast({text: 'Notifikasi belum bisa dinyalakan. Coba lagi.'}); } finally { setBusy(false); }
  };
  const test = async () => {
    try { const r = await api.pushTest(); toast({text: r.sent ? 'Tes terkirim.' : 'Tes belum sampai. Coba nyalakan ulang.'}); }
    catch { toast({text: 'Tunggu sebentar sebelum tes lagi.'}); }
  };
  return (
    <section className="card" aria-labelledby="push-h">
      <h2 id="push-h" className="h2" style={{fontWeight: 600, marginBottom: 'var(--s2)'}}>Notifikasi di HP ini</h2>
      {state === 'checking' && <Skeleton lines={1} label="Memeriksa…" />}
      {state === 'on' && (
        <div className="chips" style={{alignItems: 'center'}}>
          <span className="tag tag-green tag-lg">Menyala</span>
          <button type="button" className="btn" onClick={test}>Kirim tes</button>
          <button type="button" className="btn btn-link" onClick={() => run(disablePush)} disabled={busy}>Matikan</button>
        </div>
      )}
      {state === 'off' && (
        <div className="stack">
          <p className="body" style={{margin: 0}}>Peringatan, Pilihan ARAH, dan ringkasan pasar muncul di HP walaupun aplikasi tertutup.</p>
          <div><button type="button" className="btn btn-primary" onClick={() => run(enablePush)} disabled={busy}>Nyalakan notifikasi</button></div>
        </div>
      )}
      {state === 'denied' && <p className="body" style={{margin: 0}}>Notifikasi diblokir browser. Pakai Telegram saja?</p>}
      {(state === 'on' || state === 'off') && <PushKinds />}
      {state === 'ios-home' && <p className="body" style={{margin: 0}}>Di iPhone: buka di Safari, ketuk Bagikan, pilih "Tambahkan ke Layar Utama", lalu buka ARAH dari ikon itu.</p>}
      {state === 'unsupported' && <p className="body" style={{margin: 0}}>Browser ini tidak mendukung notifikasi. Pakai Telegram saja?</p>}
    </section>
  );
}

export function AlertsPage({onAuth, onChanged}: {onAuth: () => void; onChanged: () => void}) {
  const {num, when} = useT();
  const alerts = useLoad(api.alerts, [], onAuth);
  const del = async (a: AlertItem) => { await api.delAlert(a.id); alerts.reload(); onChanged(); };
  const groups = new Map<string, AlertItem[]>();
  for (const a of alerts.data?.items ?? []) groups.set(a.asset, [...(groups.get(a.asset) ?? []), a]);
  return (
    <>
      <div className="p-head">
        <h1 className="h1">Peringatan</h1>
        <a className="btn" href="#/cari"><Icon name="search" size={18} />Tambah peringatan</a>
      </div>
      <PushCard />
      <section className="card" aria-labelledby="al-h">
        <h2 id="al-h" className="sr-only">Daftar peringatan</h2>
        {!alerts.data ? <Skeleton lines={4} /> : groups.size === 0 ? (
          <div className="empty"><p className="body" style={{margin: 0}}>Belum ada peringatan.</p><a className="btn btn-primary" href="#/cari">Cari saham</a></div>
        ) : [...groups.entries()].map(([key, items]) => (
          <div key={key} className="agroup">
            <a href={`#/a/${encodeURIComponent(key)}`} className="row-title" style={{color: 'var(--ink)'}}>{items[0].name}</a>
            {items.map(a => (
              <div key={a.id} className="arow">
                <span>
                  {a.kind === 'verdict' ? 'Keputusan ARAH berubah'
                    : <>{a.op === '>' ? 'Naik ke' : 'Turun ke'} <b>{num(a.level, a.level < 100 ? 2 : a.decimals)}</b>{a.label ? <span className="muted"> · {a.label}</span> : null}</>}
                  {a.triggered_at && <span className="muted"> · terjadi {when(a.triggered_at)}</span>}
                </span>
                <button type="button" className="icon-btn" aria-label={`Hapus peringatan ${items[0].name}`} onClick={() => del(a)}><Icon name="close" /></button>
              </div>
            ))}
          </div>
        ))}
      </section>
    </>
  );
}
