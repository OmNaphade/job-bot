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

**Unstop and Foundit are not wired in** — both render job listings client-side (JavaScript after page load), so their real API endpoint can't be found with a plain HTTP fetch; it genuinely needs a browser's DevTools Network tab. If you want them:

1. Open the portal, run a search matching your keywords.
2. DevTools → Network → XHR/Fetch, search again, and look for the request returning job data as JSON. Also worth checking for a bare RSS link (`?format=rss`, footer link).
3. Set `UNSTOP_FEED_URL` / `FOUNDIT_FEED_URL` to what you find.

If a toggle is on but its URL/credentials are missing, that source just logs a warning and contributes nothing — it won't crash the run.

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
| `UNSTOP_FEED_URL` / `FOUNDIT_FEED_URL` | RSS/JSON feed URL, once you've found the real one | — |

None of these are secrets by nature except the Telegram token/chat id and the email address/app password — treat those four as sensitive; everything else is a public feed URL or sender address.
