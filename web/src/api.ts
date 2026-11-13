import type {SrcInfo} from './ui';
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
  key: string; name: string; name_en: string; klass: string; country: string; decimals: number; unit?: string; up_is: number;
  horizon: string; horizon_name: L; direction: Direction; summary: L; reasons: Reason[]; watch: L | null;
  snapshot: {price: number; chg1d: number | null; chg1w: number | null; chg1m: number | null; trend: string; ts: number};
  forecast: {s0: number; p_up: number; p_up_quant: number; q05: number; q25: number; q50: number; q75: number; q95: number;
    touch: Record<string, number>; band?: Band[]; vol_ratio: number; tilt_llm: number};
  vigilance: Vigilance | null; validation: Validation | null; notes: L[]; horizons?: HorizonRow[];
  history?: {t: number; c: number}[]; debate?: {bull: L | null; bear: L | null} | null;
  sources?: {title: string; source: string; url: string}[]; insight_at?: number | null; llm_enabled?: boolean;
  meta: {interval: string; steps: number; base_ts: number};
}
export interface Tile {key: string; name: string; name_en: string; decimals: number; unit?: string; price: number; chg1d: number | null; chg1w: number | null}
export interface DeskEvent {what: L; effect: L; sources: {title: string; source: string; url: string}[]}
export interface Country {name: L; summary: L | null; mood: number | null; events: DeskEvent[];
  headlines: {title: string; source: string; url: string; at: number}[]}
export type State = 'good' | 'neutral' | 'bad';
export interface SimpleCard {
  key: string; name: string; name_en: string; decimals: number; unit?: string; klass: string; country?: string; price: number;
  chg1d?: number | null; chg1m?: number | null; spark?: number[];
  now: {state: State; name: L; text: L}; next: {state: State; name: L; text: L; p_up: number; p_good?: number; range: [number, number]; dir?: 'naik' | 'datar' | 'turun' | 'belum_jelas'; odds?: {n: number; of: number}};
  gauge?: {now: number; next: number}; up_is?: number; src?: SrcInfo | null;
  why: L | null; reasons: Reason[]; watch: L | null; from_team: boolean; grade: Validation['grade'] | null;
  votes?: {up: number; down: number; none: number} | null; horizon?: string;
  touch: Record<string, number>; bca: {currency: string; buy: number; sell: number; at: number} | null;
}
export interface EventItem {at: number; country: string; title?: string; what?: L; why?: L; source: 'calendar' | 'news'; side?: 'id' | 'world';
  forecast?: string; previous?: string; impact?: string; timed?: boolean; kind?: string; note?: string}
export interface Report {days: number; total: number; right: number; wrong: number}
export interface Answer {verdict: State; confidence: 'thin' | 'fair' | 'strong'; answer: L; points: Reason[]; risk: L | null}
export interface Calc {currency: string; amount_idr: number; rate: number; source: 'bca' | 'market'; rate_at: number | null; now: number;
  next_low: number; next_high: number; plan: 'now' | 'wait' | 'split'; advice: L; summary: L}
export interface Technique {
  key: string; name: L; vote: number; strength: number; exp_ret: number | null; target: number | null; reason: L;
  hist: {n: number; n_eff: number; hit: number | null; chance: number | null} | null; weight: number; path: number[] | null;
  purpose: L; status: L & {used: boolean};
}
export interface Forecast {
  key: string; name: string; name_en: string; klass: string; country?: string; up_is: number; horizon: string; horizon_name: L; steps: number;
  s0: number; decimals: number; unit?: string; techniques: Technique[]; votes: {up: number; down: number; none: number}; tilt: number;
  conclusion: {p_up: number; q05: number; q25: number; q50: number; q75: number; q95: number; band: Band[]};
  tested: number; used: string[]; history: {t: number; c: number}[];
}
export interface SbPart {label: string | null; pct: number | null; amount: number | null}
export interface SbTerminal {
  bandar: {label: string | null; side: number; avg: SbPart; top1: SbPart; top3: SbPart; top5: SbPart; top10: SbPart;
    buyers: number | null; sellers: number | null; value: number | null} | null;
  foreign: {range: string | null; net_foreign: number | null; foreign_buy: number | null; foreign_sell: number | null; net_domestic: number | null} | null;
  insider: {name: string; date: string; at: number | null; action: string; side: number; nationality: string; change_shares: number | null;
    change_pct: number | null; now_pct: number | null; price: string}[] | null;
  stream: {text: string; at: string; likes: number; replies: number; type: string; url: string}[] | null;
  at: number;
}
export interface Bar {t: number; o: number; h: number; l: number; c: number; v: number}
export interface LiveData {
  key: string; source: 'stockbit' | 'binance' | 'yahoo' | 'daily'; realtime: boolean; bars: Bar[]; last: number; prev: number | null;
  chg_pct: number | null; delay_min?: number; at: number; note?: L; decimals?: number; unit?: string;
  book?: {bids: {price: number; lots: number}[]; offers: {price: number; lots: number}[]; foreign_net: number | null};
}
export interface Simple {
  horizon?: string;
  indonesia: SimpleCard | null; usd: SimpleCard | null; cny: SimpleCard | null;
  abroad?: {now: {state: State; name: L; text: L}; next: {state: State; name: L; p_good?: number}; gauge?: {now: number; next: number}; countries: SimpleCard[]};
  headline?: string | null; headline_us?: string | null;
}
export interface Brief {
  at: number; mode: 'team' | 'rules'; headline: L; outlook: L | null; simple?: Simple;
  events?: EventItem[]; foreign?: {side: 'buy' | 'sell'; text: L; sources: {title: string; source: string; url: string}[]} | null; report?: Report;
  world: {stance: string; name: L; summary: L; points: {text: L}[]};
  tiles: Tile[]; assets: AssetView[]; countries: Record<string, Country>;
}
export interface RecCard {
  key: string; name: string; country: string; decimals: number; unit?: string; price: number; chg1d: number | null;
  strengths: L[]; risks: L[]; why: L; p_up_1m: number; pe: number | null; tag?: TagInfo | null; score?: number | null;
  plan: {entry: [number, number]; stop: number; targets: [number, number]; rr: number}; spark: number[];
  currency?: 'IDR' | 'USD'; sector?: string | null; liquidity?: number | null; lot_size?: number; min_capital?: number;
  horizon_days?: number; held?: boolean;
}
export interface RecordInfo {horizon: string; n: number; hits: number; pct: number | null; pending: number; enough: boolean}
export interface PicksRecord {closed: number; open: number; target: number; stop: number; expired: number;
  items: {asset: string; status: 'target' | 'stop' | 'expired'; made_at: number; closed_at: number; ret: number | null}[]}
export interface Recs {at: number | null; ID: RecCard[]; US: RecCard[]; screened: {ID: number; US: number}; record?: PicksRecord; profile?: RiskProfile | null}
export interface MarketRow {
  key: string; name: string; name_en: string; decimals: number; unit?: string; price: number; chg1d: number | null; chg1w: number | null;
  direction: Direction; p_up: number; q05: number; q95: number; vigilance: Vigilance | null; spark: number[];
  klass?: string; tag?: TagInfo | null; score?: number | null; up_is?: number; src?: SrcInfo | null; chg1m?: number | null;
}
export interface TrackRow {horizon: string; name: L; n: number; calls: number; call_hits: number; brier: number | null;
  brier_quant: number | null; cover90: number | null}
export interface Track {
  report: Report; live: {by_horizon: TrackRow[]; pending: number; scored: number};
  tests: {key: string; name: string; name_en: string; horizons: Record<string, Validation>}[];
  validating: boolean; validated_at: number | null;
}
export interface Status {
  version: string; revision?: string;
  recs?: {at: number | null; screened: {ID: number; US: number} | null; missing?: {ID: number; US: number} | null}; data_at: number | null; data_errors: Record<string, string>; news_at: number | null;
  llm_enabled: boolean; llm_error: {kind: string} | null; models: {provider: string; quick: string; deep: string; fallback: string | null}; llm_last: {provider: string; fallback: boolean; at: number} | null; claude_calls_today: number;
  budget: {day: number; month: number; cap_day: number; cap_month: number; over: boolean};
  telegram_enabled: boolean; stockbit?: {configured: boolean; usable?: boolean; refresh_until?: number | null; error?: {kind: string} | null};
  schedule: {slot: string; time: string}[]; timezone: string;
}
export interface AlertItem {id: number; asset: string; name: string; decimals: number; unit?: string; op: string; level: number;
  kind?: 'price' | 'verdict'; grp?: string | null; label?: string | null;
  triggered_at: number | null; last_price: number | null}

export interface TagInfo {key: string; label: string; icon: string; tone: 'green' | 'grey' | 'orange'}
export interface StockVerdict {
  key: string; verdict: 'masuk' | 'bertahap' | 'tunggu' | 'hindari'; label: L; icon: string; tone: TagInfo['tone']; sentence: string;
  score: number | null; p_up: number | null;
  parts: Record<string, {points: number; max: number}>;
  reasons: {part: string; share: number; good: boolean; text: L}[]; tested: boolean; at: number;
}
export interface Story {id: string; topic: string; country: string; title: string; source: string; url: string; published_at: number; outlets: number;
  sources?: string[]; impact?: 'positif' | 'negatif' | 'netral'; tickers?: string[]}
export interface Feed {scope: string; topics: string[]; items: Story[];
  desks: {country: string; summary: L | null; mood: number | null; events: DeskEvent[]}[]}
export interface TickerFeed {key: string; items: Story[]; posts: NonNullable<SbTerminal['stream']>}
export interface History {key: string; range: string; decimals: number; unit: string; bars: Bar[]}
export interface PushInfo {key: string; devices: number; last: {at: number; title: string; sent: number} | null}

export interface QuickRow {key: string; name: string; name_en: string; klass: string; country: string; unit: string; decimals: number;
  up_is: number; price: number | null; chg1d: number | null; chg1m?: number | null; spark: number[]; tag: TagInfo | null; alerts?: number; src?: SrcInfo | null}
export interface PlanLevel {level: number; label: string; kind: 'stop' | 'target' | 'band'}
export interface PlanInfo {key: string; name: string; klass: string; price: number | null; decimals: number; unit: string; from_plan: boolean;
  plan: {entry: [number, number]; stop: number; targets: [number, number]; rr: number} | null; levels: PlanLevel[]}
export interface PulseInfo {state: 'live' | 'delayed' | 'paused'; at: number | null; since: number | null; stockbit: boolean; delay_min: number;
  alerts_active: number; telegram: boolean; idx?: {key: string; label: string; open: boolean; day: boolean}}
export interface PanelRow {key: string; label: string; price: number | null; chg1m: number | null; decimals?: number; unit?: string; src: SrcInfo | null}
export interface FlowRow {key: string; name: string; net: number; at: number | null}
export interface PanelInfo {
  session: {key: string; label: string; open: boolean};
  foreign: {day: {net_foreign: number; foreign_buy: number | null; foreign_sell: number | null; range?: string} | null;
    buy: FlowRow[]; sell: FlowRow[]; covered: number; at: number | null; source: string | null};
  commodities: PanelRow[]; macro: PanelRow[];
  factors: Record<'ID' | 'US', Factor[]>; profile: RiskProfile | null;
  news: Record<'ID' | 'US', {count: number; href: string; top: {text: string; direction: string; url: string} | null}>;
}
export interface SimOut {q05: number; q50: number; q95: number; p_up?: number}
export interface SimItem {key: string; name: string; sector: string | null; tag: TagInfo | null; price: number; currency: 'IDR' | 'USD';
  units: number; unit: string; cost: number; stop: number; loss_at_stop: number; target1: number; outcomes: Record<string, SimOut>}
export interface SimResult {capital: number; market: 'ID' | 'US'; fx: number | null; profile: string | null; items: SimItem[]; cash: number;
  invested?: number; horizons: string[]; total?: Record<string, SimOut> | null; loss_at_stops?: number; need?: {key: string; rp: number} | null}
export type RiskProfile = 'hati-hati' | 'sedang' | 'berani';
export interface Factor {label: string; side: number | null; value: number | null; kind: 'pct' | 'idr'; href?: string}

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
  brief: () => call<{brief: Brief | null; building: boolean; llm_error: 'credit' | 'auth' | 'limit' | 'error' | null; llm_enabled: boolean; record?: RecordInfo}>('/api/brief'),
  calc: (amount: number, currency: string) => call<Calc>(`/api/calc?amount=${amount}&currency=${currency}`),
  ask: (question: string) => call<Answer>('/api/ask', {method: 'POST', body: JSON.stringify({question})}),
  runBrief: () => call<{started: boolean}>('/api/brief/run', {method: 'POST'}),
  markets: (group: string, horizon: string) => call<{rows: MarketRow[]}>(`/api/markets?group=${group}&horizon=${horizon}`),
  asset: (key: string, horizon: string) => call<AssetView>(`/api/asset/${encodeURIComponent(key)}?horizon=${encodeURIComponent(horizon)}`),
  analyze: (key: string) => call(`/api/asset/${encodeURIComponent(key)}/analyze`, {method: 'POST'}),
  recs: () => call<Recs>('/api/recs'),
  forecast: (key: string, h: string) => call<Forecast>(`/api/forecast/${encodeURIComponent(key)}?h=${h}`),
  live: (key: string) => call<LiveData>(`/api/live/${encodeURIComponent(key)}`),
  stockbit: (key: string) => call<SbTerminal>(`/api/stockbit/${encodeURIComponent(key)}`),
  simple: (h: string) => call<Simple>(`/api/simple?h=${h}`),
  track: () => call<Track>('/api/track'),
  status: () => call<Status>('/api/status'),
  settings: () => call<{lang: Lang; levels: Record<string, number[]>; assets: {key: string; name: string}[]}>('/api/settings'),
  saveSettings: (body: {lang?: Lang; levels?: Record<string, number[]>}) =>
    call<{lang: Lang; levels: Record<string, number[]>}>('/api/settings', {method: 'PUT', body: JSON.stringify(body)}),
  alerts: () => call<{items: AlertItem[]}>('/api/alerts'),
  addAlert: (asset: string, op: string, level: number) =>
    call<{items: AlertItem[]}>('/api/alerts', {method: 'POST', body: JSON.stringify({asset, op, level})}),
  verdict: (key: string) => call<StockVerdict>(`/api/verdict/${encodeURIComponent(key)}`),
  history: (key: string, range: string) => call<History>(`/api/history/${encodeURIComponent(key)}?range=${range}`),
  feed: (scope: string, topic?: string) => call<Feed>(`/api/feed?scope=${scope}${topic ? `&topic=${topic}` : ''}`),
  tickerFeed: (key: string) => call<TickerFeed>(`/api/feed/${encodeURIComponent(key)}`),
  pushInfo: () => call<PushInfo>('/api/push/key'),
  pushSubscribe: (sub: PushSubscriptionJSON) => call<{devices: number}>('/api/push/subscribe', {method: 'POST', body: JSON.stringify(sub)}),
  pushUnsubscribe: (endpoint: string) => call<{devices: number}>('/api/push/unsubscribe', {method: 'POST', body: JSON.stringify({endpoint})}),
  pushTest: () => call<{sent: number}>('/api/push/test', {method: 'POST'}),
  search: (q: string) => call<{q: string; items: QuickRow[]}>(`/api/search?q=${encodeURIComponent(q)}`),
  watchlist: () => call<{items: QuickRow[]}>('/api/watchlist'),
  watch: (key: string, on: boolean) => call<{items: string[]; on: boolean}>('/api/watchlist', {method: 'POST', body: JSON.stringify({key, on})}),
  plan: (key: string) => call<PlanInfo>(`/api/plan/${encodeURIComponent(key)}`),
  addAlerts: (asset: string, levels: {level: number; label?: string}[], verdict_change: boolean) =>
    call<{group: string; count: number}>('/api/alerts/batch', {method: 'POST', body: JSON.stringify({asset, levels, verdict_change})}),
  undoAlerts: (group: string) => call<{items: AlertItem[]}>(`/api/alerts/group/${encodeURIComponent(group)}`, {method: 'DELETE'}),
  pulse: () => call<PulseInfo>('/api/pulse'),
  panel: () => call<PanelInfo>('/api/panel'),
  simulate: (capital: number, market: string) => call<SimResult>(`/api/simulate?capital=${Math.round(capital)}&market=${market}`),
  setProfile: (profile: RiskProfile) => call<{profile: RiskProfile}>('/api/profile', {method: 'POST', body: JSON.stringify({profile})}),
  stockbitSession: (value: string) => call('/api/stockbit/session', {method: 'POST', body: JSON.stringify({value})}),
  askTelegram: (question: string, answer: string) => call<{sent: boolean}>('/api/ask/telegram', {method: 'POST', body: JSON.stringify({question, answer})}),
  delAlert: (id: number) => call<{items: AlertItem[]}>(`/api/alerts/${id}`, {method: 'DELETE'}),
};
