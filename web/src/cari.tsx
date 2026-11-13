/* Cari and Tanya ARAH (redesign pack prompt 05, mockup MobileCari.html). */
import {useEffect, useRef, useState} from 'react';
import {api, type Answer, type QuickRow} from './api';
import {openAlertSheet} from './alertsheet';
import {useT} from './i18n';
import {Icon, Skeleton, VerdictTag, toast} from './ui';

const OFTEN = ['Saham apa yang layak masuk hari ini?', 'Rupiah minggu depan ke mana?', 'Kenapa IHSG turun sebulan ini?'];
const WORD = {good: 'Mendukung', neutral: 'Seimbang', bad: 'Menekan'} as const;

/** The answer to one question, with a way to keep it in Telegram. */
export function AskAnswer({question, onDone}: {question: string; onDone?: () => void}) {
  const {l} = useT();
  const [a, setA] = useState<Answer | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setA(null); setFailed(false);
    api.ask(question).then(x => { if (live) { setA(x); onDone?.(); } }).catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question, tick]);
  const send = async () => {
    if (!a) return;
    try { await api.askTelegram(question, `${l(a.answer)}\n${a.points.map(p => `• ${l(p.text)}`).join('\n')}`); toast({text: 'Terkirim ke Telegram.'}); }
    catch { toast({text: 'Telegram belum tersambung. Atur di server dulu.'}); }
  };
  if (failed) return (
    <div className="answer-box" role="alert">
      <p className="body" style={{margin: 0}}>ARAH belum bisa menjawab. <button type="button" className="btn-link btn" onClick={() => setTick(tick + 1)}>Coba lagi</button></p>
    </div>
  );
  if (!a) return <div className="answer-box"><Skeleton lines={3} label="ARAH sedang menyusun jawaban…" /></div>;
  return (
    <div className="answer-box" aria-live="polite">
      <span className="caption">{question}</span>
      <p className="row-title" style={{margin: 0}}>{WORD[a.verdict]} · {l(a.answer)}</p>
      <ul>{a.points.map((p, i) => <li key={i}>{l(p.text)}</li>)}</ul>
      {a.risk && <p className="caption" style={{margin: 0}}>Risiko: {l(a.risk)}</p>}
      <div><button type="button" className="btn" onClick={send}>Kirim ke Telegram</button></div>
    </div>
  );
}

function ResultRow({r, onPick}: {r: QuickRow; onPick?: () => void}) {
  const {num} = useT();
  return (
    <li className="res-row">
      <a href={`#/a/${encodeURIComponent(r.key)}`} onClick={onPick}>
        <span className="row-title">{r.klass === 'stock' ? r.key : r.name}</span>
        <span className="muted">{r.klass === 'stock' ? r.name : r.key}</span>
      </a>
      <VerdictTag tag={r.tag} />
      <span className="res-px">{r.price != null ? num(r.price, r.price < 100 ? 2 : r.decimals) : ''}</span>
      <button type="button" className="icon-btn outlined" aria-label={`Pasang peringatan ${r.key}`} onClick={() => openAlertSheet(r.key)}>
        <Icon name="bell" />
      </button>
    </li>
  );
}

/** Shared by the phone Cari page and the desktop header dropdown. */
export function SearchPanel({q, onPick}: {q: string; onPick?: () => void}) {
  const [rows, setRows] = useState<QuickRow[] | null>(null);
  const [asked, setAsked] = useState<string | null>(null);
  const query = q.trim();
  useEffect(() => {
    setAsked(null);
    if (!query) { setRows([]); return; }
    setRows(null);
    const id = window.setTimeout(() => { api.search(query).then(r => setRows(r.items)).catch(() => setRows([])); }, 180);
    return () => window.clearTimeout(id);
  }, [query]);
  const ask = (text: string) => setAsked(text);
  return (
    <div>
      {query && (
        <>
          <p className="sect-lbl">Saham</p>
          {rows == null ? <Skeleton lines={2} label="Mencari…" /> : rows.length === 0 ? <p className="body" style={{margin: 'var(--s3) 0'}}>Tidak ada saham atau pasar yang cocok.</p> : (
            <ul className="res">{rows.map(r => <ResultRow key={r.key} r={r} onPick={onPick} />)}</ul>
          )}
          <p className="sect-lbl">Tanya ARAH</p>
          <button type="button" className="ask-row" onClick={() => ask(query)}>
            <Icon name="chat" /><span className="grow">"{query}"</span><Icon name="next" />
          </button>
        </>
      )}
      {asked && <AskAnswer question={asked} />}
      {!query && !asked && (
        <>
          <p className="sect-lbl" style={{borderBottom: 0}}>Sering ditanya</p>
          <div className="stack">
            {OFTEN.map(x => <button key={x} type="button" className="chip-q" style={{justifyContent: 'flex-start'}} onClick={() => ask(x)}>{x}</button>)}
          </div>
        </>
      )}
    </div>
  );
}

export function CariPage() {
  const [q, setQ] = useState('');
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => { input.current?.focus(); }, []);
  return (
    <section aria-label="Cari saham atau tanya ARAH">
      <div className="cari-bar">
        <label className="cari-field">
          <Icon name="search" />
          <input ref={input} type="search" value={q} onChange={e => setQ(e.target.value)} placeholder="Cari saham atau tanya ARAH" aria-label="Cari saham atau tanya ARAH" />
          {q && <button type="button" className="icon-btn" aria-label="Hapus" onClick={() => { setQ(''); input.current?.focus(); }}><Icon name="close" /></button>}
        </label>
        <a href="#/" className="btn btn-link">Batal</a>
      </div>
      <SearchPanel q={q} />
    </section>
  );
}
