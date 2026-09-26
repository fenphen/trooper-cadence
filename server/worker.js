/* Mention Finder API — a tiny Cloudflare Worker that searches Reddit through its
 * official OAuth API on behalf of the Mention Finder page.
 *
 *   GET /search?q=...&t=week[&sub=name][&after=t3_x]  -> Reddit post listing (trimmed)
 *   GET /about?user=name                              -> account age and karma
 *   GET /health                                       -> { ok: true }
 *
 * Secrets:  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET   (from reddit.com/prefs/apps)
 * Vars:     ALLOWED_ORIGINS (comma list), REDDIT_USERNAME (for the User-Agent Reddit requires)
 * Optional: LIMITER rate-limit binding (see wrangler.toml)
 */

const TIMES = new Set(['hour', 'day', 'week', 'month', 'year', 'all']);
const SUB_RE = /^[A-Za-z0-9_]{2,21}$/;
const USER_RE = /^[A-Za-z0-9_-]{3,20}$/;
const AFTER_RE = /^t3_[a-z0-9]{1,13}$/;
const CACHE_SECONDS = 60;

class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

let token = null; // { value, expires } — reused while this Worker instance stays warm

const userAgent = env => `web:mention-finder:v1.0 (by /u/${env.REDDIT_USERNAME || 'unknown'})`;

async function getToken(env, force) {
  if (!force && token && token.expires > Date.now() + 60_000) return token.value;
  if (!env.REDDIT_CLIENT_ID || !env.REDDIT_CLIENT_SECRET) throw new HttpError(503, 'server not configured: missing Reddit credentials');
  const res = await fetch('https://www.reddit.com/api/v1/access_token', {
    method: 'POST',
    headers: {
      Authorization: 'Basic ' + btoa(`${env.REDDIT_CLIENT_ID}:${env.REDDIT_CLIENT_SECRET}`),
      'Content-Type': 'application/x-www-form-urlencoded',
      'User-Agent': userAgent(env),
    },
    body: 'grant_type=client_credentials',
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.access_token) throw new HttpError(502, `Reddit sign-in failed (${res.status}${data.error ? ': ' + data.error : ''})`);
  token = { value: data.access_token, expires: Date.now() + (data.expires_in || 3600) * 1000 };
  return token.value;
}

async function reddit(env, path, params) {
  const url = 'https://oauth.reddit.com' + path + '?' + new URLSearchParams(Object.assign({ raw_json: '1' }, params));
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await fetch(url, { headers: { Authorization: 'Bearer ' + await getToken(env, attempt > 0), 'User-Agent': userAgent(env) } });
    if (res.status === 401 && attempt === 0) continue; // token expired early — refresh once
    if (res.status === 429) throw new HttpError(429, 'Reddit rate limit reached; try again in a minute');
    if (res.status === 404) throw new HttpError(404, 'not found');
    if (!res.ok) throw new HttpError(502, `Reddit returned ${res.status}`);
    return res.json();
  }
  throw new HttpError(502, 'Reddit sign-in rejected');
}

// Only the fields the page uses, so this can't serve as a general Reddit proxy.
function trimPost(p) {
  return {
    id: p.id, created_utc: p.created_utc, subreddit: p.subreddit, author: p.author,
    title: p.title, selftext: (p.selftext || '').slice(0, 5000), score: p.score, num_comments: p.num_comments,
    permalink: p.permalink, is_self: p.is_self, url: p.url, url_overridden_by_dest: p.url_overridden_by_dest, over_18: p.over_18,
  };
}

async function search(env, qs) {
  const q = (qs.get('q') || '').trim();
  const t = qs.get('t') || 'week';
  const sub = qs.get('sub') || '';
  const after = qs.get('after') || '';
  if (!q || q.length > 512) throw new HttpError(400, 'q must be 1–512 characters');
  if (!TIMES.has(t)) throw new HttpError(400, 'bad t');
  if (sub && !SUB_RE.test(sub)) throw new HttpError(400, 'bad sub');
  if (after && !AFTER_RE.test(after)) throw new HttpError(400, 'bad after');
  const params = { q, sort: 'new', t, limit: '100', type: 'link' };
  if (sub) params.restrict_sr = '1';
  if (after) params.after = after;
  const data = await reddit(env, sub ? `/r/${sub}/search` : '/search', params);
  const listing = (data && data.data) || {};
  return {
    data: {
      after: listing.after || null,
      children: (listing.children || []).filter(c => c.kind === 't3').map(c => ({ kind: 't3', data: trimPost(c.data) })),
    },
  };
}

async function about(env, qs) {
  const user = qs.get('user') || '';
  if (!USER_RE.test(user)) throw new HttpError(400, 'bad user');
  const d = ((await reddit(env, `/user/${user}/about`, {})) || {}).data || {};
  if (!d.created_utc) throw new HttpError(404, 'suspended or deleted');
  return { data: { created_utc: d.created_utc, total_karma: d.total_karma, link_karma: d.link_karma, comment_karma: d.comment_karma } };
}

function corsHeaders(env, origin) {
  const allowed = (env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!origin || !allowed.includes(origin)) return null;
  return { 'Access-Control-Allow-Origin': origin, 'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Max-Age': '86400', Vary: 'Origin' };
}

const json = (body, status, extra) => new Response(JSON.stringify(body), {
  status: status || 200,
  headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, extra),
});

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const cors = corsHeaders(env, request.headers.get('Origin'));
    if (request.method === 'OPTIONS') return new Response(null, { status: cors ? 204 : 403, headers: cors || {} });
    if (url.pathname === '/health') return json({ ok: true, configured: !!(env.REDDIT_CLIENT_ID && env.REDDIT_CLIENT_SECRET) }, 200, cors || {});
    if (!cors) return json({ error: 'origin not allowed' }, 403);
    if (request.method !== 'GET') return json({ error: 'method not allowed' }, 405, cors);

    const route = { '/search': search, '/about': about }[url.pathname];
    if (!route) return json({ error: 'not found' }, 404, cors);

    // Per-visitor limit, so one person can't use up the site's Reddit quota.
    if (env.LIMITER) {
      const { success } = await env.LIMITER.limit({ key: request.headers.get('CF-Connecting-IP') || 'unknown' });
      if (!success) return json({ error: 'too many searches; wait a minute' }, 429, Object.assign({ 'Retry-After': '60' }, cors));
    }

    // Identical searches within a minute are served from cache (saves Reddit quota).
    const cache = typeof caches !== 'undefined' ? caches.default : null;
    const cacheKey = new Request(url.origin + url.pathname + '?' + [...url.searchParams].sort().map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&'));
    if (cache) {
      const hit = await cache.match(cacheKey);
      if (hit) return new Response(hit.body, { status: hit.status, headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8', 'X-Cache': 'HIT' }, cors) });
    }

    try {
      const body = await route(env, url.searchParams);
      const res = json(body, 200, { 'Cache-Control': `public, max-age=${CACHE_SECONDS}` });
      if (cache) ctx.waitUntil(cache.put(cacheKey, res.clone()));
      return new Response(res.body, { status: 200, headers: Object.assign({ 'Content-Type': 'application/json; charset=utf-8' }, cors) });
    } catch (e) {
      const status = e instanceof HttpError ? e.status : 500;
      return json({ error: e instanceof HttpError ? e.message : 'internal error' }, status, Object.assign(status === 429 ? { 'Retry-After': '60' } : {}, cors));
    }
  },
};
