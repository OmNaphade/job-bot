# Setting up the real sources

Everything is disabled by default. Nothing runs against a live source until you turn it on **and** provide the matching credentials/URL below. No secret values live in this repo or in this doc — only variable names, what they're for, and non-secret defaults. Real values go in `backend/.env` (gitignored) locally, or GitHub repository secrets for the scheduled runner.

## Telegram alerts (required for notifications)

1. Create a bot via [@BotFather](https://t.me/BotFather) → note the bot token.
2. Message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to read back your `chat_id`.
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars before starting the backend.

Without these, ingestion still runs and stores matches — it just skips sending (logged, not an error).

## LinkedIn / Naukri via email alerts (Tier B — never scrapes)

1. In your LinkedIn/Naukri account, create a saved job search matching what you want, and turn on email alerts for it.
2. Point those alerts at a dedicated inbox (a separate Gmail works well — don't reuse an inbox you don't want a bot reading).
3. For Gmail, create an [App Password](https://myaccount.google.com/apppasswords) (regular password won't work over IMAP).
4. Set: `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD`, and optionally `ALERT_EMAIL_IMAP_HOST`/`ALERT_EMAIL_IMAP_PORT` if not using Gmail. `LINKEDIN_ALERT_SENDER`/`NAUKRI_ALERT_SENDER` default to the standard alert sender addresses — override only if yours differ.
5. Enable `enable_linkedin_alerts`/`enable_naukri_alerts` via `PUT /ingestion/settings` or the Flutter settings screen.

**Note:** the HTML parsing in `email_parsers.py` was written against the well-known structure of these alert emails but hasn't been validated against a live sample. If postings are missed once real alerts arrive, that's a small, isolated fix in that one file — not a sign anything else is broken.

## RSS/JSON sources (Tier A)

Six real, verified, publicly-published feeds are wired in and work out of the box — just turn on `enable_rss_sources`:

- **WeWorkRemotely** (`weworkremotely`) — remote programming jobs RSS.
- **Himalayas** (`himalayas`) — remote jobs RSS, includes a structured company-name field.
- **Remotive** (`remotive`) — remote jobs RSS.
- **NoDesk** (`nodesk`) — remote jobs RSS (note the feed is at `/index.xml`, not `/feed/`).
- **Jobspresso** (`jobspresso`) — curated remote jobs RSS.
- **RemoteOK** (`remoteok`) — JSON API (their RSS feed was discontinued/410 Gone; the JSON API is the current public replacement). Uses a separate adapter (`RemoteOkAdapter`) since it's JSON, not RSS/Atom, and their API 403s requests with no `User-Agent` header at all — a descriptive UA is sent to identify the client, which is not evasion of a login wall or JS rendering.

All are legitimate feeds/APIs meant for exactly this kind of consumption — no scraping involved. Override the matching env var (`WEWORKREMOTELY_FEED_URL`, `HIMALAYAS_FEED_URL`, `REMOTIVE_FEED_URL`, `NODESK_FEED_URL`, `JOBSPRESSO_FEED_URL`, `REMOTEOK_API_URL`) if you want a different feed than the defaults.

Unstop and Foundit are both client-side-rendered with no public feed/RSS, but both *are* wired in — each via its own internal listing/search API rather than a documented one, see below.

## Direct-from-company-site sources (Tier C)

Greenhouse, Lever, and Ashby each publish a public per-company JSON API meant for embedding that company's own job listings on their careers page. Consuming it isn't scraping — no HTML parsing, no login wall, no JS rendering — but it is direct-from-a-single-company rather than an aggregator, so these are gated by the **`allow_direct_scraping`** ingestion setting (Flutter settings screen or `PUT /ingestion/settings`), separately from the RSS toggle.

1. Find the company's board token/slug from their careers page URL:
   - Greenhouse: `boards.greenhouse.io/<token>` (or `<token>.greenhouse.io`)
   - Lever: `jobs.lever.co/<slug>`
   - Ashby: `jobs.ashbyhq.com/<name>`
2. Set the matching env var to a comma-separated list of tokens — `GREENHOUSE_BOARD_TOKENS`, `LEVER_COMPANY_SLUGS`, `ASHBY_BOARD_NAMES`. Each token becomes its own adapter, registered automatically (`app/ingestion/adapters/safe_registry.py`), sourced as `greenhouse:<token>` / `lever:<slug>` / `ashby:<name>` in the `jobs` table.
3. Turn on `allow_direct_scraping`.

Not every company uses one of these three ATS platforms, and a guessed token that doesn't exist just 404s — logged as a warning, contributes zero candidates, doesn't break the run (same graceful-degradation pattern as every other adapter). A fully custom company careers page (not on a known ATS) has no public API to call and would need bespoke, more fragile HTML scraping — not implemented here.

## Foundit and Unstop (reverse-engineered internal APIs — read this before enabling)

Neither Foundit nor Unstop has a documented public feed or API. Both are instead queried via their own **internal** endpoints — the same ones each site's own search page calls client-side — found by inspecting live network traffic / testing endpoint shapes directly, not from any published documentation. Both return clean JSON with no login required.

This is a different tier of trust from every other source in this file:
- Greenhouse/Lever/Ashby and the RSS/JSON feeds are all officially published, documented-or-obviously-intended for exactly this kind of consumption.
- These two are neither — undocumented, could change shape or disappear without notice, not guaranteed stable.

Given that, both are gated by **`allow_direct_scraping`** (same toggle as the ATS adapters) rather than `enable_rss_sources`, and treated as opt-in/use-at-your-own-risk rather than sources you can rely on long-term. If either changes its endpoint or tightens bot-blocking further, the adapter will start failing quietly (logged as a warning, contributing zero candidates, same graceful-degradation pattern as everything else) rather than break the run — but don't be surprised if either needs revisiting down the line.

**Risk assessment (read before enabling — not a legal opinion, just what was actually checked):**

- **robots.txt** — checked directly for both. Foundit's disallows `/middleware/`, `/pwa/`, a handful of other paths, and does **not** list `/home/api/searchResultsPage`; the path this adapter calls isn't excluded. Unstop's robots.txt explicitly has `Allow: /api/public/*` (more specific than its later `Disallow: /api/*`), and the endpoint this adapter calls — `/api/public/opportunity/search-result` — falls directly under that explicit allow. Unstop's robots.txt also explicitly blocks known scraper/downloader tools (HTTrack, Wget, CCBot, etc.); this project doesn't use any of them or try to mirror the site.
- **Terms of Service** — both sites' ToS pages are themselves client-side-rendered (same JS-shell issue as their job listings), so the actual legal text couldn't be read via a plain HTTP fetch — this was checked and hit the same wall. Nobody involved has read either site's full ToS. If you want certainty here, open both terms pages in a real browser and read the automated-access/scraping clauses yourself, or ask a lawyer — this repo can't give that assurance.
- **Volume** — both adapters are called once per scheduled ingestion run (hourly by default, configurable), a single GET request per run per configured query. This is closer to a human doing one search than a scraper hammering an endpoint; there's no retry loop, no concurrency, no polling faster than the configured interval.
- **Data touched** — only public job-posting metadata (title/company/location/link), the same fields a human browsing the search page would see, not scraped en masse or republished anywhere — it flows into your own private `jobs` table and a Telegram message to you.
- **Foundit's bot-blocking specifically is a signal worth weighing** — it shows Foundit has *some* active anti-automation posture, even though the specific path we call isn't in their robots.txt disallow list. Robots.txt and WAF rules aren't necessarily written by the same team or kept in sync, so this is a real, if soft, signal that Foundit doesn't want undeclared automated traffic in general — not just conclusive proof this specific integration is unwelcome.

None of this amounts to a legal guarantee — it's the concrete, checkable facts, not a substitute for reading the actual ToS or getting real legal advice if this matters to you. The lower-frequency, low-volume, personal-use nature of this bot meaningfully reduces (but doesn't eliminate) both ban risk and any hypothetical legal exposure.

### Foundit

`FounditAdapter` (`app/ingestion/adapters/foundit_adapter.py`) calls `https://www.foundit.in/home/api/searchResultsPage`. Its edge (Akamai) keyword-blocks any `User-Agent` whose first token contains the literal substring `bot` (verified directly — `job-alert-bot/1.0` gets `403`, `job-alert-ingestion-client/1.0` does not; `curl` and `requests`' own default UA both pass with no browser pretense at all — and a `job-bot` substring appearing later in the string, e.g. inside a URL, does *not* trigger it either). `FounditAdapter` therefore uses a different, still fully honest and self-identifying UA than the rest of the project's adapters — not a browser spoof, just avoiding one word that trips a naive filter. Like every adapter in this project, its UA also includes a `+https://github.com/OmNaphade/job-bot` link back to this repo, so anyone curious (or wanting to block it) can see exactly what's making the request and why — the same convention Googlebot's own UA uses.

1. Set `FOUNDIT_SEARCH_QUERIES` — comma-separated broad search terms (e.g. `java,python,devops`). Each becomes its own adapter instance, sourced as `foundit:<query>` in the `jobs` table. The actual title/company/location filtering still happens afterwards via your normal include/exclude keywords, same as every other source — these just need to be broad enough to surface real candidates.
2. Set `FOUNDIT_SEARCH_LOCATIONS` (e.g. `pune`) — required; if unset, no Foundit adapters are registered at all, regardless of `FOUNDIT_SEARCH_QUERIES` or the toggle.
3. Optionally `FOUNDIT_SEARCH_COUNTRIES` (defaults to `India`).
4. Turn on `allow_direct_scraping`.

### Unstop

`UnstopAdapter` (`app/ingestion/adapters/unstop_adapter.py`) calls `https://unstop.com/api/public/opportunity/search-result`. Unlike Foundit, no keyword-blocking was found on the User-Agent, and no query parameter was found that narrows results server-side either — it just fetches the latest ~50 open job postings in bulk (`oppstatus=open`) and relies on the normal include/exclude keyword matching afterwards, same as the RSS sources. No per-query configuration needed — just turn on `allow_direct_scraping` and it's active, sourced as `unstop` in the `jobs` table.

## Sources evaluated and NOT wired in

The following were checked (live HTTP fetch, not guessed) and have no public RSS/JSON feed a plain HTTP client can consume — each was either login-gated, renders job listings client-side via JavaScript, is paywalled, has discontinued its feed, or isn't actually a job-listings source:

| Source | Why not |
|---|---|
| Naukri | No official feed (handled instead via email alerts — see above) |
| LinkedIn | No public feed (handled instead via email alerts — see above) |
| Fiverr | Gig marketplace, not a job-postings board |
| Upwork | RSS saved-search feed discontinued (`410 Gone`) |
| Indeed | RSS discontinued (`404`) |
| Remote Rocketship | Blocked by Cloudflare bot-challenge on plain GET |
| Eztrackr | It's an application-tracker tool/extension, not a job board — no listings to feed |
| Toptal | Application-gated freelance platform, no public feed |
| Skip The Drive | Feed URLs return the HTML page, not XML — non-functional |
| FlexJobs | Subscription/paywalled, no public feed |
| Remote.co | Feed endpoint unreachable (likely bot-protected); unconfirmed either way |
| AngelList / Wellfound | No official public feed |
| Freelancer.com | `/jobs/rss` returns an HTML search page, not real RSS/XML |
| Working Nomads | `/jobs/rss` returns the Angular SPA shell, not RSS — client-side rendered |
| SimplyHired | No working public feed found |
| Stack Overflow Jobs | Shut down March 2022 |
| Glassdoor | No public feed, login required |
| Monster | No public feed |
| CareerCloud | No public feed |
| CareerBuilder | No public feed |

If any of these later publish a genuine feed, wire it in the same way as the others: add an env var + default in `backend/app/core/config.py`, then register an `RssAdapter` (or a dedicated adapter, if the format isn't RSS/Atom) in `backend/app/ingestion/adapters/safe_registry.py`.

## Configuring environment variables

Copy `backend/.env.example` to `backend/.env` and fill in real values — it's loaded automatically at startup (via `python-dotenv`) and is gitignored, so secrets never get committed. No need to mess with `setx` or per-terminal `$env:` exports.

## Environment variables reference

| Variable | Purpose | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | — |
| `TELEGRAM_CHAT_ID` | Your chat id to send alerts to | — |
| `ALERT_EMAIL_ADDRESS` | Inbox the bot reads alert emails from | — |
| `ALERT_EMAIL_APP_PASSWORD` | IMAP app password for that inbox | — |
| `ALERT_EMAIL_IMAP_HOST` | IMAP host | `imap.gmail.com` |
| `ALERT_EMAIL_IMAP_PORT` | IMAP port | `993` |
| `LINKEDIN_ALERT_SENDER` | Sender address to filter LinkedIn alert emails | `jobalerts-noreply@linkedin.com` |
| `NAUKRI_ALERT_SENDER` | Sender address to filter Naukri alert emails | `noreply@naukri.com` |
| `WEWORKREMOTELY_FEED_URL` | RSS feed URL | `weworkremotely.com/categories/remote-programming-jobs.rss` |
| `HIMALAYAS_FEED_URL` | RSS feed URL | `himalayas.app/jobs/rss` |
| `REMOTIVE_FEED_URL` | RSS feed URL | `remotive.com/remote-jobs/feed` |
| `NODESK_FEED_URL` | RSS feed URL | `nodesk.co/remote-jobs/index.xml` |
| `JOBSPRESSO_FEED_URL` | RSS feed URL | `jobspresso.co/feed/` |
| `REMOTEOK_API_URL` | JSON API URL | `remoteok.com/api` |
| `GREENHOUSE_BOARD_TOKENS` | Comma-separated Greenhouse board tokens (also needs `allow_direct_scraping` on) | — |
| `LEVER_COMPANY_SLUGS` | Comma-separated Lever company slugs (also needs `allow_direct_scraping` on) | — |
| `ASHBY_BOARD_NAMES` | Comma-separated Ashby board names (also needs `allow_direct_scraping` on) | — |
| `FOUNDIT_SEARCH_QUERIES` | Comma-separated broad search terms (also needs `allow_direct_scraping` on and `FOUNDIT_SEARCH_LOCATIONS` set) | — |
| `FOUNDIT_SEARCH_LOCATIONS` | Location passed to Foundit's search (required for any Foundit adapter to register) | — |
| `FOUNDIT_SEARCH_COUNTRIES` | Country passed to Foundit's search | `India` |

Unstop has no env var of its own — it's controlled entirely by the `allow_direct_scraping` toggle, no per-query configuration.

None of these are secrets by nature except the Telegram token/chat id and the email address/app password — treat those four as sensitive; everything else is a public feed URL or sender address.
