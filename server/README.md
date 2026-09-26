# Mention Finder API (small server)

Reddit stopped answering anonymous searches from websites in May 2026. This small server
signs in to **Reddit's official API** and runs the searches for the Mention Finder page.
It runs on **Cloudflare Workers**, which is free at this size, with nothing to maintain.
GitHub deploys it for you, so you never need a command line.

What it does:
- `GET /search?q=…&t=week&sub=…` searches Reddit posts (newest first) and returns only the fields the page shows.
- `GET /about?user=…` returns an account's age and karma.
- `GET /health` tells you whether it's running and has its Reddit keys.

Built-in protections:
- Only your site (`https://fenphen.github.io`) is allowed to use it.
- Each visitor is limited to 30 requests a minute.
- Identical searches within a minute are served from a cache.
- Your Reddit keys stay in Cloudflare and never reach the browser.

Comments: Reddit's official API doesn't offer comment search, so comment results still
come from PullPush when it's up. The page's "Search comments on Reddit" button always works.

---

## One-time setup (about 20 minutes, plus waiting for Reddit)

### 1. Get Reddit API access (Reddit has to approve it)
Since November 2025, Reddit approves every new API app by hand under its
[Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy).

1. Signed in to Reddit, open that page and submit an **API access request**. Describe the use honestly, for example:
   *"Mention Finder: a free, non-commercial public website that lets people search recent Reddit posts
   mentioning a name or website, including misspellings. Read-only search of public posts, newest first.
   Under 100 requests per minute, results cached for 60 seconds, no data stored, no AI training.
   Site: https://fenphen.github.io/trooper-cadence/mention-finder/"*
2. Once approved, go to <https://www.reddit.com/prefs/apps> and click **create app**:
   - name: `mention-finder`
   - type: **web app**
   - redirect uri: `https://fenphen.github.io/trooper-cadence/mention-finder/` (required by the form, but not used)
3. Note down two values:
   - **Client ID:** the short code under the app's name.
   - **Secret:** labelled "secret".

If you already have a Reddit app from before November 2025, its ID and secret should still work.

### 2. Create a free Cloudflare account
1. Sign up at <https://dash.cloudflare.com/sign-up>.
2. Open **Workers & Pages** once and choose your free `workers.dev` subdomain.
3. Note down your **Account ID**. It's shown on the Workers & Pages overview, in the right-hand column.
4. Go to **My Profile → API Tokens → Create Token**, use the **"Edit Cloudflare Workers"** template, and create it.
   Copy the token (it's only shown once).

### 3. Give GitHub the keys
In GitHub, open **fenphen/trooper-cadence → Settings → Secrets and variables → Actions**.

Under **Secrets → New repository secret**, add these four:

| Name | Value |
|---|---|
| `CLOUDFLARE_API_TOKEN` | the token from step 2 |
| `CLOUDFLARE_ACCOUNT_ID` | your Cloudflare Account ID |
| `REDDIT_CLIENT_ID` | the Reddit client ID |
| `REDDIT_CLIENT_SECRET` | the Reddit secret |

Under the **Variables** tab → **New repository variable**, add these two:

| Name | Value |
|---|---|
| `DEPLOY_API` | `true` |
| `REDDIT_USERNAME` | your Reddit username, without `u/` (Reddit requires it in requests) |

### 4. Deploy
Go to **Actions → Deploy Mention Finder API → Run workflow**. When it goes green, open the run log.
Near the end is the server address, like `https://mention-finder-api.YOUR-SUBDOMAIN.workers.dev`.

Check it: open `https://mention-finder-api.YOUR-SUBDOMAIN.workers.dev/health` in a browser.
It should show `{"ok":true,"configured":true}`.

It also redeploys automatically whenever files in `server/` change on `main`.

### 5. Point the website at it
Edit [`mention-finder/config.js`](../mention-finder/config.js) on GitHub (pencil icon), set
`API: 'https://mention-finder-api.YOUR-SUBDOMAIN.workers.dev'`, and commit. After a minute or two,
searches on the site will return results again.

---

## Limits and costs
- **Cloudflare free plan:** 100,000 requests a day. Each search uses 1–3.
- **Reddit's free tier:** about 100 requests a minute for non-commercial use. The cache and per-visitor limit keep usage well under that.
- **Changing limits:** edit `server/wrangler.toml`. `limit` sets requests per visitor per minute, and `ALLOWED_ORIGINS` sets which websites may use the server.

## For developers
- `node server/test.mjs` runs the tests (Reddit is mocked). GitHub runs them before every deploy.
- For a local run: `npx wrangler dev` inside `server/`, with `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` in `server/.dev.vars`. Never commit that file.
