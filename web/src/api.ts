export type L = {id: string; en: string};
export type Lang = 'id' | 'en';
export type Direction = 'up' | 'down' | 'flat';

export interface HorizonRow {
  horizon: string; name: L; p_up: number; direction: Direction;
  q05: number; q50: number; q95: number; touch: Record<string, number>; thin: boolean;
}
export interface Reason {text: L; lean: number}
export interface Vigilance {code: 'aman' | 'waspada' | 'siaga' | 'bahaya'; name: L; level: number; p: number}
export interface Validation {grade: 'validated' | 'range_only' | 'experimental' | 'insufficient'; n?: number; hit_rate?: number; cover90?: number}
export interface Band {step: number; q05: number; q25: number; q50: number; q75: number; q95: number}
export interface AssetView {
  key: string; name: string; name_en: string; klass: string; country: string; decimals: number; up_is: number;
  horizon: string; horizon_name: L; direction: Direction; summary: L; reasons: Reason[]; watch: L | null;
  snapshot: {price: number; chg1d: number | null; chg1w: number | null; chg1m: number | null; trend: string; ts: number};
  forecast: {s0: number; p_up: number; p_up_quant: number; q05: number; q25: number; q50: number; q75: number; q95: number;
    touch: Record<string, number>; band?: Band[]; vol_ratio: number; tilt_llm: number};
  vigilance: Vigilance | null; validation: Validation | null; notes: L[]; horizons?: HorizonRow[];
  history?: {t: number; c: number}[]; debate?: {bull: L | null; bear: L | null} | null;
  sources?: {title: string; source: string; url: string}[]; insight_at?: number | null; llm_enabled?: boolean;
  meta: {interval: string; steps: number; base_ts: number};
}
export interface Tile {key: string; name: string; name_en: string; decimals: number; price: number; chg1d: number | null; chg1w: number | null}
export interface DeskEvent {what: L; effect: L; sources: {title: string; source: string; url: string}[]}
export interface Country {name: L; summary: L | null; mood: number | null; events: DeskEvent[];
  headlines: {title: string; source: string; url: string; at: number}[]}
export interface Brief {
  at: number; mode: 'team' | 'rules'; headline: L;
  world: {stance: string; name: L; summary: L; points: {text: L}[]};
  tiles: Tile[]; assets: AssetView[]; countries: Record<string, Country>;
}
export interface RecCard {
  key: string; name: string; country: string; decimals: number; price: number; chg1d: number | null;
  strengths: L[]; risks: L[]; why: L; p_up_1m: number; pe: number | null;
  plan: {entry: [number, number]; stop: number; targets: [number, number]; rr: number}; spark: number[];
}
export interface Recs {at: number | null; ID: RecCard[]; US: RecCard[]; screened: {ID: number; US: number}}
export interface MarketRow {
  key: string; name: string; name_en: string; decimals: number; price: number; chg1d: number | null; chg1w: number | null;
  direction: Direction; p_up: number; q05: number; q95: number; vigilance: Vigilance | null; spark: number[];
}
export interface TrackRow {horizon: string; name: L; n: number; calls: number; call_hits: number; brier: number | null;
  brier_quant: number | null; cover90: number | null}
export interface Track {
  live: {by_horizon: TrackRow[]; pending: number; scored: number};
  tests: {key: string; name: string; name_en: string; horizons: Record<string, Validation>}[];
  validating: boolean; validated_at: number | null;
}
export interface Status {
  version: string; data_at: number | null; data_errors: Record<string, string>; news_at: number | null;
  llm_enabled: boolean; llm_error: {kind: string} | null; models: {provider: string; quick: string; deep: string; fallback: string | null}; llm_last: {provider: string; fallback: boolean; at: number} | null; claude_calls_today: number;
  budget: {day: number; month: number; cap_day: number; cap_month: number; over: boolean};
  telegram_enabled: boolean; schedule: {slot: string; time: string}[]; timezone: string;
}
export interface AlertItem {id: number; asset: string; name: string; decimals: number; op: string; level: number;
  triggered_at: number | null; last_price: number | null}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, ...init});
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail ?? detail; } catch { /* body was not JSON */ }
    throw new ApiError(r.status, String(detail));
  }
  return r.json() as Promise<T>;
}

export const api = {
  session: () => call<{auth_required: boolean; authed: boolean; lang: Lang; version: string}>('/api/session'),
  login: (password: string) => call('/api/login', {method: 'POST', body: JSON.stringify({password})}),
  logout: () => call('/api/logout', {method: 'POST'}),
  brief: () => call<{brief: Brief | null; building: boolean; llm_error: 'credit' | 'auth' | 'limit' | 'error' | null}>('/api/brief'),
  runBrief: () => call<{started: boolean}>('/api/brief/run', {method: 'POST'}),
  markets: (group: string, horizon: string) => call<{rows: MarketRow[]}>(`/api/markets?group=${group}&horizon=${horizon}`),
  asset: (key: string, horizon: string) => call<AssetView>(`/api/asset/${encodeURIComponent(key)}?horizon=${encodeURIComponent(horizon)}`),
  analyze: (key: string) => call(`/api/asset/${encodeURIComponent(key)}/analyze`, {method: 'POST'}),
  recs: () => call<Recs>('/api/recs'),
  track: () => call<Track>('/api/track'),
  status: () => call<Status>('/api/status'),
  settings: () => call<{lang: Lang; levels: Record<string, number[]>; assets: {key: string; name: string}[]}>('/api/settings'),
  saveSettings: (body: {lang?: Lang; levels?: Record<string, number[]>}) =>
    call<{lang: Lang; levels: Record<string, number[]>}>('/api/settings', {method: 'PUT', body: JSON.stringify(body)}),
  alerts: () => call<{items: AlertItem[]}>('/api/alerts'),
  addAlert: (asset: string, op: string, level: number) =>
    call<{items: AlertItem[]}>('/api/alerts', {method: 'POST', body: JSON.stringify({asset, op, level})}),
  delAlert: (id: number) => call<{items: AlertItem[]}>(`/api/alerts/${id}`, {method: 'DELETE'}),
};
