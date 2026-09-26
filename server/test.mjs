// Tests for worker.js with Reddit mocked. Run: node server/test.mjs
import assert from 'node:assert/strict';
import worker from './worker.js';

const ORIGIN = 'https://fenphen.github.io';
const env = { REDDIT_CLIENT_ID: 'id', REDDIT_CLIENT_SECRET: 'secret', ALLOWED_ORIGINS: ORIGIN, REDDIT_USERNAME: 'tester' };
const ctx = { waitUntil() {} };

let calls = [];
let redditMode = 'ok';
globalThis.fetch = async (url, init = {}) => {
  url = String(url);
  calls.push({ url, init });
  if (url.includes('/api/v1/access_token')) {
    assert.equal(init.headers.Authorization, 'Basic ' + btoa('id:secret'));
    assert.match(init.headers['User-Agent'], /by \/u\/tester/);
    return Response.json({ access_token: 'tok' + calls.length, expires_in: 3600 });
  }
  assert.match(init.headers.Authorization, /^Bearer tok/);
  if (redditMode === '401once') { redditMode = 'ok'; return new Response('', { status: 401 }); }
  if (redditMode === '429') return new Response('', { status: 429 });
  if (url.includes('/user/')) {
    if (url.includes('/user/gone/')) return Response.json({ data: { is_suspended: true } });
    return Response.json({ data: { created_utc: 1600000000, total_karma: 42, link_karma: 1, comment_karma: 41, email: 'secret-field' } });
  }
  return Response.json({ data: { after: 't3_next', children: [
    { kind: 't3', data: { id: 'a1', created_utc: 1, subreddit: 'deals', author: 'u1', title: 'bestbuy', selftext: 'x'.repeat(9000), score: 5, num_comments: 2, permalink: '/r/deals/comments/a1/x/', is_self: true, url: 'u', secret_field: 'nope' } },
  ] } });
};

const req = (path, origin = ORIGIN, method = 'GET') =>
  worker.fetch(new Request('https://api.example.workers.dev' + path, { method, headers: origin ? { Origin: origin } : {} }), env, ctx);

// CORS: other sites are refused, preflight works for ours
assert.equal((await req('/search?q=x', 'https://evil.example')).status, 403);
assert.equal((await req('/search?q=x', null)).status, 403);
let r = await req('/search?q=x', ORIGIN, 'OPTIONS');
assert.equal(r.status, 204);
assert.equal(r.headers.get('Access-Control-Allow-Origin'), ORIGIN);

// Search: validated, signed in once, trimmed output, CORS header present
calls = [];
r = await req('/search?q=' + encodeURIComponent('"bestbuy.com" OR bestbuy') + '&t=week&sub=deals');
assert.equal(r.status, 200);
assert.equal(r.headers.get('Access-Control-Allow-Origin'), ORIGIN);
let body = await r.json();
assert.equal(body.data.after, 't3_next');
assert.equal(body.data.children[0].data.title, 'bestbuy');
assert.equal(body.data.children[0].data.selftext.length, 5000);
assert.equal(body.data.children[0].data.secret_field, undefined);
const searchCall = calls.find(c => c.url.includes('oauth.reddit.com'));
assert.match(searchCall.url, /\/r\/deals\/search\?/);
assert.match(searchCall.url, /restrict_sr=1/);
assert.match(searchCall.url, /sort=new/);

// Token is reused across requests
calls = [];
await req('/search?q=chewy');
assert.equal(calls.filter(c => c.url.includes('access_token')).length, 0);

// Expired token -> refreshed once, still succeeds
redditMode = '401once';
calls = [];
r = await req('/search?q=chewy');
assert.equal(r.status, 200);
assert.equal(calls.filter(c => c.url.includes('access_token')).length, 1);

// Reddit rate limit is passed on as 429
redditMode = '429';
r = await req('/search?q=chewy');
assert.equal(r.status, 429);
assert.equal(r.headers.get('Retry-After'), '60');
redditMode = 'ok';

// Bad input
for (const bad of ['/search', '/search?q=x&t=forever', '/search?q=x&sub=a/b', '/search?q=x&after=../../x', '/search?q=' + 'x'.repeat(600), '/about?user=a/b']) {
  assert.equal((await req(bad)).status, 400, bad);
}
assert.equal((await req('/nope')).status, 404);

// Account info: only public fields; suspended -> 404
body = await (await req('/about?user=someone')).json();
assert.deepEqual(body, { data: { created_utc: 1600000000, total_karma: 42, link_karma: 1, comment_karma: 41 } });
assert.equal((await req('/about?user=gone')).status, 404);

// Per-visitor limiter
const limited = await worker.fetch(new Request('https://x.dev/search?q=a', { headers: { Origin: ORIGIN } }),
  Object.assign({}, env, { LIMITER: { limit: async () => ({ success: false }) } }), ctx);
assert.equal(limited.status, 429);

// Health, and missing credentials
body = await (await worker.fetch(new Request('https://x.dev/health'), { ALLOWED_ORIGINS: ORIGIN }, ctx)).json();
assert.deepEqual(body, { ok: true, configured: false });

console.log('server tests passed');
