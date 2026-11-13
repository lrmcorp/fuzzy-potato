// ARAH relay: forwards ARAH's market-data requests to Yahoo Finance and Stockbit from Cloudflare's
// network, for a server whose own address those sites refuse.
//
// Locked down on purpose:
// - Every request must carry the x-relay-key header equal to the RELAY_KEY secret of this Worker.
// - Only read paths are forwarded (price charts, fundamentals, Stockbit charts and order book),
//   plus Stockbit's token refresh. Nothing that places orders or changes an account.
// - Nothing is logged or stored here.
//
// Paste this whole file into the Worker's code editor (Cloudflare dashboard), then add the secret
// RELAY_KEY under Settings > Variables and Secrets.

const UPSTREAM = {
  yahoo: ['https://query1.finance.yahoo.com', 'https://query2.finance.yahoo.com'],
  stockbit: ['https://exodus.stockbit.com'],
};
const ALLOW = {
  yahoo: [/^\/v8\/finance\/chart\/[^/]+$/, /^\/ws\/fundamentals-timeseries\/v1\/finance\/timeseries\/[^/]+$/],
  stockbit: [/^\/charts\//, /^\/company-price-feed\//],
};
const STOCKBIT_REFRESH = '/login/refresh';

function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export default {
  async fetch(request, env) {
    if (!env.RELAY_KEY || env.RELAY_KEY.length < 24) return new Response('relay key not set', {status: 500});
    if (!same(request.headers.get('x-relay-key') || '', env.RELAY_KEY)) return new Response('forbidden', {status: 403});

    const url = new URL(request.url);
    const [, service, ...rest] = url.pathname.split('/');
    const path = '/' + rest.join('/');
    const hosts = UPSTREAM[service];
    if (!hosts || path.includes('..') || path.toLowerCase().includes('%2e')) return new Response('not allowed', {status: 404});

    const refresh = service === 'stockbit' && path === STOCKBIT_REFRESH && request.method === 'POST';
    const read = request.method === 'GET' && ALLOW[service].some(r => r.test(path));
    if (!refresh && !read) return new Response('not allowed', {status: 404});

    const headers = {'user-agent': 'Mozilla/5.0', accept: request.headers.get('accept') || 'application/json'};
    if (service === 'stockbit') {
      const auth = request.headers.get('authorization');
      if (auth) headers.authorization = auth;
      headers.origin = 'https://stockbit.com';
      headers.referer = 'https://stockbit.com/';
      headers['content-type'] = 'application/json';
    }
    const body = refresh ? await request.text() : undefined;

    let res;
    for (const host of hosts) {
      res = await fetch(host + path + url.search, {method: request.method, headers, body, redirect: 'follow'});
      if (res.status !== 429) break; // Yahoo: try the second host once
    }
    return new Response(res.body, {
      status: res.status,
      headers: {'content-type': res.headers.get('content-type') || 'application/json', 'cache-control': 'no-store'},
    });
  },
};
