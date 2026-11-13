import type {ReactNode} from 'react';
import {Banner} from '@astryxdesign/core/Banner';
import {Button} from '@astryxdesign/core/Button';
import {Skeleton} from '@astryxdesign/core/Skeleton';
import type {AssetView, Direction, HorizonRow, Reason, Validation, Vigilance} from './api';
import type {Loaded} from './hooks';
import {useT} from './i18n';

export const GLYPH: Record<Direction, string> = {up: '▲', down: '▼', flat: '◆'};

export function Glyph({d}: {d: Direction}) {
  const {t} = useT();
  return <span className={`glyph glyph-${d}`} role="img" aria-label={t(d)}>{GLYPH[d]}</span>;
}

export function Change({value, label}: {value: number | null | undefined; label: string}) {
  const {pct} = useT();
  if (value == null) return null;
  return <span className="change">{pct(value)} <span className="muted">{label}</span></span>;
}

/** The seven steps from one hour to one month. Each cell is a button that selects that horizon. */
export function HorizonStrip({rows, selected, onSelect}: {rows: HorizonRow[]; selected?: string; onSelect?: (h: string) => void}) {
  const {t, l} = useT();
  return (
    <div className="strip" role={onSelect ? 'group' : undefined} aria-label={onSelect ? t('pick_horizon') : undefined}>
      {rows.map(r => {
        const body = (
          <>
            <span className="strip-h">{l(r.name)}</span>
            <span className="strip-d"><Glyph d={r.direction} /> {Math.round(r.p_up * 100)}%</span>
            <span className="strip-w">{t(r.direction)}{r.thin ? ' *' : ''}</span>
          </>
        );
        return onSelect ? (
          <button key={r.horizon} type="button" className="strip-cell" aria-pressed={selected === r.horizon}
            onClick={() => onSelect(r.horizon)}>{body}</button>
        ) : <div key={r.horizon} className="strip-cell">{body}</div>;
      })}
    </div>
  );
}

export function Reasons({items}: {items: Reason[]}) {
  const {l, t} = useT();
  if (!items.length) return null;
  return (
    <ul className="reasons">
      {items.map((r, i) => (
        <li key={i}>
          <span className="mark" role="img" aria-label={r.lean > 0 ? t('bull') : r.lean < 0 ? t('bear') : ''}>
            {r.lean > 0 ? '▲' : r.lean < 0 ? '▼' : '•'}
          </span>
          <span>{l(r.text)}</span>
        </li>
      ))}
    </ul>
  );
}

export function VigilanceLine({v, decimals, horizonName, unit = 'Rp'}: {v: Vigilance; decimals: number; horizonName: string; unit?: string}) {
  const {t, l, money} = useT();
  return (
    <p className={`vigil vigil-${v.code}`}>
      <span className="vigil-tag">{t('watch_level')}: {l(v.name)}</span>
      <span>{t('touch')} {money(v.level, decimals, unit)} {t('within')} {horizonName}: <strong>{Math.round(v.p * 100)}%</strong></span>
    </p>
  );
}

export function GradeNote({v}: {v: Validation | null}) {
  const {t} = useT();
  const key = v ? (`g_${v.grade}` as const) : 'g_pending';
  return <p className="note">{t(key)}</p>;
}

export function Verdict({view}: {view: AssetView}) {
  const {l, t, money} = useT();
  return (
    <>
      <p className="verdict">{l(view.summary)}</p>
      {Object.keys(view.forecast.touch).length > 0 && !view.vigilance && (
        <p className="note">{Object.entries(view.forecast.touch).map(([lv, p]) =>
          `${t('touch')} ${money(Number(lv), view.decimals, view.unit)}: ${Math.round(p * 100)}%`).join(' · ')}</p>
      )}
    </>
  );
}

export function Async<T>({state, children, skeleton}: {state: Loaded<T>; children: (data: T) => ReactNode; skeleton?: ReactNode}) {
  const {t} = useT();
  if (state.data) return <>{children(state.data)}</>;
  if (state.error) {
    return (
      <Banner status="error" title={t('load_failed')} description={state.error.message}
        endContent={<Button label={t('retry')} size="sm" onClick={state.reload} />} />
    );
  }
  return <div aria-busy="true" aria-label={t('loading')}>{skeleton ?? <Lines n={5} />}</div>;
}

export function Lines({n}: {n: number}) {
  return (
    <div className="lines">
      {Array.from({length: n}, (_, i) => <Skeleton key={i} height={18} width={`${92 - ((i * 17) % 40)}%`} index={i} />)}
    </div>
  );
}

export function AssetLink({k, children}: {k: string; children: ReactNode}) {
  return <a className="asset-link" href={`#/a/${k}`}>{children}</a>;
}
