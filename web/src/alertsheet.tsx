/* One alert sheet for every entry point: search results, the watchlist, the asset page and a pick's plan.
   The direction of a price alert follows from the current price, so there is no up/down select. */
import {useEffect, useState} from 'react';
import {api, type PlanInfo} from './api';
import {useT} from './i18n';
import {Sheet, Skeleton, toast} from './ui';
import {pushState, enablePush} from './push';

type Opener = (key: string, opts?: {allPlan?: boolean}) => void;
let opener: Opener | null = null;
/** Opens the alert sheet for an asset from anywhere in the app. */
export const openAlertSheet: Opener = (key, opts) => opener?.(key, opts);

export function AlertSheetHost({onChanged, telegram}: {onChanged: () => void; telegram: boolean}) {
  const [req, setReq] = useState<{key: string; allPlan?: boolean} | null>(null);
  useEffect(() => {
    opener = (key, opts) => setReq({key, ...opts});
    return () => { opener = null; };
  }, []);
  if (!req) return null;
  return <AlertSheet k={req.key} allPlan={req.allPlan} telegram={telegram} onClose={() => setReq(null)} onSaved={onChanged} />;
}

function AlertSheet({k, allPlan, telegram, onClose, onSaved}: {k: string; allPlan?: boolean; telegram: boolean; onClose: () => void; onSaved: () => void}) {
  const {num} = useT();
  const [plan, setPlan] = useState<PlanInfo | null>(null);
  const [failed, setFailed] = useState(false);
  const [custom, setCustom] = useState('');
  const [picked, setPicked] = useState<Record<number, boolean>>({});
  const [verdict, setVerdict] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [push, setPush] = useState<string>('checking');
  const [tgInfo, setTgInfo] = useState(false);

  useEffect(() => {
    api.plan(k).then(p => {
      setPlan(p);
      // From a pick's trade plan every level starts checked; elsewhere the user chooses.
      if (allPlan && p.from_plan) setPicked(Object.fromEntries(p.levels.map((_, i) => [i, true])));
    }).catch(() => setFailed(true));
    void pushState().then(setPush);
  }, [k, allPlan]);

  const price = plan?.price ?? null;
  const d = plan?.decimals ?? 0;
  // Typed the way it is shown: "7.300" or "7300" (dots are thousands, a comma is the decimal point).
  const customVal = Number(custom.replace(/[\s.]/g, '').replace(',', '.').replace(/^rp/i, ''));
  const customOk = custom.trim() !== '' && customVal > 0;
  const chosen = plan ? plan.levels.filter((_, i) => picked[i]) : [];
  const count = chosen.length + (customOk ? 1 : 0) + (verdict ? 1 : 0);
  const isStock = plan?.klass === 'stock';

  const save = async () => {
    if (!plan) return;
    setBusy(true); setErr(null);
    try {
      const levels = [...chosen.map(x => ({level: x.level, label: x.label})), ...(customOk ? [{level: customVal, label: 'Harga pilihan'}] : [])];
      const r = await api.addAlerts(k, levels, verdict);
      onClose(); onSaved();
      toast({text: `${r.count} peringatan aktif`, action: {label: 'Batalkan', run: () => { void api.undoAlerts(r.group).then(onSaved); }}});
    } catch {
      setErr('Peringatan belum terpasang. Coba lagi.');
    } finally { setBusy(false); }
  };

  return (
    <Sheet title={`Kabari saya soal ${k}`} onClose={onClose}>
      {!plan && !failed && <Skeleton lines={4} label="Memuat harga…" />}
      {failed && <p className="err">Data belum cukup untuk peringatan ini.</p>}
      {plan && (
        <>
          <label className="field">
            <span>Harga lain</span>
            <input inputMode="decimal" value={custom} onChange={e => setCustom(e.target.value)}
              placeholder={price ? `mis. ${num(Math.round(price * 1.04), d)}` : 'mis. 7.300'} />
            {customOk && price != null && (
              <span className="caption">{customVal > price ? 'Kabari saat naik ke' : 'Kabari saat turun ke'} {num(customVal, d)} (kini {num(price, d)})</span>
            )}
          </label>
          {plan.levels.map((lv, i) => (
            <label key={i} className="opt">
              <input type="checkbox" checked={!!picked[i]} onChange={e => setPicked({...picked, [i]: e.target.checked})} />
              <span className="opt-main">{price != null && lv.level > price ? 'Naik ke' : 'Turun ke'} <b>{num(lv.level, d)}</b></span>
              <span className={`opt-note ${lv.kind}`}>{lv.label}</span>
            </label>
          ))}
          {isStock && (
            <label className="opt">
              <input type="checkbox" checked={verdict} onChange={e => setVerdict(e.target.checked)} />
              <span className="opt-main">Keputusan ARAH berubah</span>
            </label>
          )}
          <div className="deliver">
            <span>Kirim ke: <b>{push === 'on' ? 'HP ini' : 'Aplikasi saja'}</b></span>
            {push !== 'on' && push !== 'unsupported' && push !== 'checking' && (
              <button type="button" className="btn" onClick={async () => setPush(await enablePush())}>Nyalakan di HP ini</button>
            )}
            {telegram ? <span className="caption">+ Telegram</span>
              : <button type="button" className="btn" onClick={() => setTgInfo(!tgInfo)} aria-expanded={tgInfo}>+ Telegram</button>}
          </div>
          {push === 'denied' && <p className="caption">Notifikasi diblokir browser. Pakai Telegram saja?</p>}
          {tgInfo && !telegram && (
            <p className="caption">Telegram belum tersambung. Buat bot di @BotFather, lalu pasang TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID di server (lihat Atur).</p>
          )}
          {err && <p className="err" role="alert">{err}</p>}
          <button type="button" className="btn btn-primary btn-block" disabled={!count || busy} onClick={save}>
            {busy ? 'Memasang…' : count ? `Pasang ${count} peringatan` : 'Pilih minimal satu'}
          </button>
        </>
      )}
    </Sheet>
  );
}
