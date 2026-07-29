# Job Alert Platform

Job Alert Platform is a continuously-running job-monitoring bot with a FastAPI backend and a Flutter dashboard. It polls job sources on a schedule, matches new postings against your saved keyword preferences, and pushes a Telegram alert the moment something new matches — without you needing to open the app. It's designed to collect job postings without relying on unsafe direct scraping of platforms such as LinkedIn or Naukri.

## Overview

The application has three main layers:

- **Backend API**: FastAPI service exposing job, preference, ingestion-settings, and ingestion endpoints.
- **Ingestion pipeline**: a background scheduler runs the same pipeline the API exposes manually — fetch candidate jobs from enabled sources, match them against saved keywords, deduplicate against previously-seen jobs, persist new ones, and send a Telegram digest.
- **Frontend UI**: a Flutter dashboard that displays stored jobs, lets you trigger an on-demand check, and configures sources/keywords. It's a secondary control panel — the backend keeps running and alerting on its own schedule whether or not the app is open.

## Architecture

### Backend

- `backend/main.py`
  - FastAPI application bootstrap with a `lifespan` hook: initializes the database and starts the background scheduler on startup, stops the scheduler on shutdown.
  - Registers CORS middleware and the API router.
- `backend/app/api/routes.py`
  - HTTP endpoints for health checks, jobs, preferences, ingestion settings, and ingestion. Services are wired in via FastAPI `Depends`.
- `backend/app/services/`
  - `job_service.py` / `preference_service.py` / `ingestion_settings_service.py`: business logic, one service per entity.
  - `errors.py`: `DuplicateResourceError`, raised by repositories on a uniqueness conflict and translated to `HTTPException(409)` in routes.
- `backend/app/repositories/`
  - `job_repository.py` / `preference_repository.py` / `ingestion_settings_repository.py`: SQLite persistence, one repository per entity.
- `backend/app/db/database.py`
  - `init_db()`: creates all tables once at startup (not per-request).
  - `db_session()`: a context manager that commits on success, rolls back on error, and always closes the connection.
- `backend/app/ingestion/`
  - `scheduler.py`: wraps an APScheduler `BackgroundScheduler` that runs the ingestion pipeline on an interval (`poll_interval_hours`, configurable at runtime).
  - `services/ingestion_service.py`: orchestrates one ingestion run — build the adapter registry from current settings, build the matcher from current keyword preferences, fetch, match, dedup, persist, notify.
  - `services/matcher_service.py`: include/exclude keyword matching against title/company/location.
  - `services/dedup_service.py`: in-batch dedup (catches two adapters returning the same link in one run). Cross-run dedup is handled atomically at the DB layer via `jobs.link UNIQUE` + `INSERT OR IGNORE`.
  - `services/notification_service.py`: sends a Telegram digest message for newly-persisted matches.
  - `adapters/rss_adapter.py`: fetches and parses a configured RSS/JSON feed (Tier A sources).
  - `adapters/email_adapter.py` + `adapters/email_parsers.py`: reads LinkedIn/Naukri job-alert emails via IMAP and parses postings out of the HTML body (Tier B — never talks to linkedin.com/naukri.com directly).
- `backend/app/core/config.py`
  - Static/secret configuration read from environment variables (Telegram token/chat id, IMAP credentials, alert sender addresses, feed URLs).
- `backend/scripts/run_ingestion_once.py`
  - Short-lived entrypoint for a single ingestion pass — what the GitHub Actions scheduled workflow actually runs, as opposed to the long-running `main.py` + APScheduler used for local/always-on operation.

### Frontend

- `frontend/lib/main.dart` — app entry point and Material 3 theme (light/dark).
- `frontend/lib/screens/home_screen.dart` — dashboard showing stored jobs (source-colored cards, tap to copy the link) and an on-demand "Check for new jobs now" trigger.
- `frontend/lib/screens/config_screen.dart` — loads/saves real ingestion source toggles and poll interval against the backend.
- `frontend/lib/screens/keyword_config_screen.dart` — loads current saved keywords and updates include/exclude filters.
- `frontend/lib/services/api_service.dart` — the only place that talks HTTP to the backend.
- `frontend/lib/widgets/section_label.dart` — shared small section-header widget.

## Backend data model and schema

### SQLite tables

- `jobs`
  - `id`, `title`, `company`, `location`, `link` (UNIQUE — the sole dedup key), `source`, `posted_at`
- `preferences`
  - `id`, `keyword`, `kind` (`include` or `exclude`), `location` (stored, not yet used in matching); `UNIQUE(keyword, kind)`
- `ingestion_settings`
  - Single row (`id = 1`): `enable_rss_sources`, `enable_linkedin_alerts`, `enable_naukri_alerts`, `allow_direct_scraping`, `poll_interval_hours`

There is no separate "seen jobs" table — `jobs.link` being `UNIQUE`, combined with an atomic `INSERT OR IGNORE`, is the single dedup mechanism.

## API reference

- `GET /health` → `{"status": "ok"}`
- `GET /jobs` / `POST /jobs` (409 on duplicate `link`)
- `GET /preferences` / `POST /preferences` (body includes `kind: "include"|"exclude"`, 409 on duplicate) / `DELETE /preferences/{id}`
- `GET /ingestion/settings` / `PUT /ingestion/settings` — reading/updating source toggles and poll interval; updating the interval reschedules the background job immediately, no restart needed.
- `POST /ingest` — runs the ingestion pipeline immediately (same logic the scheduler runs automatically).
- `POST /ingest/keywords` — bulk-replaces the `include`/`exclude` preference lists:
  ```json
  { "include_keywords": ["backend", "flutter", "python"], "exclude_keywords": ["senior", "manager"] }
  ```

## Setting up the real sources

Everything is disabled by default. Nothing runs against a live source until you turn it on **and** provide the matching credentials/URL below.

### Telegram alerts (required for notifications)

1. Create a bot via [@BotFather](https://t.me/BotFather) → note the bot token.
2. Message your bot once, then visit `https://api.telegram.org/bot<TOKEN>/getUpdates` to read back your `chat_id`.
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars before starting the backend.

Without these, ingestion still runs and stores matches — it just skips sending (logged, not an error).

### LinkedIn / Naukri via email alerts (Tier B — never scrapes)

1. In your LinkedIn/Naukri account, create a saved job search matching what you want, and turn on email alerts for it.
2. Point those alerts at a dedicated inbox (a separate Gmail works well — don't reuse an inbox you don't want a bot reading).
3. For Gmail, create an [App Password](https://myaccount.google.com/apppasswords) (regular password won't work over IMAP).
4. Set: `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD`, and optionally `ALERT_EMAIL_IMAP_HOST`/`ALERT_EMAIL_IMAP_PORT` if not using Gmail. `LINKEDIN_ALERT_SENDER`/`NAUKRI_ALERT_SENDER` default to the standard alert sender addresses — override only if yours differ.
5. Enable `enable_linkedin_alerts`/`enable_naukri_alerts` via `PUT /ingestion/settings` or the Flutter settings screen.

**Note:** the HTML parsing in `email_parsers.py` was written against the well-known structure of these alert emails but hasn't been validated against a live sample. If postings are missed once real alerts arrive, that's a small, isolated fix in that one file — not a sign anything else is broken.

### RSS/JSON sources (Tier A)

Two real, verified, publicly-published feeds are wired in and work out of the box — just turn on `enable_rss_sources`:

- **WeWorkRemotely** (`weworkremotely`) — remote programming jobs RSS.
- **Himalayas** (`himalayas`) — remote jobs RSS, includes a structured company-name field.

Both are legitimate RSS feeds meant for exactly this kind of consumption — no scraping involved. Override `WEWORKREMOTELY_FEED_URL`/`HIMALAYAS_FEED_URL` if you want a different category feed than the defaults.

**Unstop and Foundit are not wired in** — both render job listings client-side (JavaScript after page load), so their real API endpoint can't be found with a plain HTTP fetch; it genuinely needs a browser's DevTools Network tab. If you want them:

1. Open the portal, run a search matching your keywords.
2. DevTools → Network → XHR/Fetch, search again, and look for the request returning job data as JSON. Also worth checking for a bare RSS link (`?format=rss`, footer link).
3. Set `UNSTOP_FEED_URL` / `FOUNDIT_FEED_URL` to what you find.

If a toggle is on but its URL/credentials are missing, that source just logs a warning and contributes nothing — it won't crash the run.

## Configuring environment variables

Copy `backend/.env.example` to `backend/.env` and fill in real values — it's loaded automatically at startup (via `python-dotenv`) and is gitignored, so secrets never get committed. No need to mess with `setx` or per-terminal `$env:` exports.

## Environment variables

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
| `UNSTOP_FEED_URL` / `FOUNDIT_FEED_URL` | RSS/JSON feed URL, once you've found the real one | — |

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM edit .env with real values, then:
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

The scheduler starts automatically with the app — as long as this process is running, it polls every `poll_interval_hours` and alerts on new matches with no further interaction. This assumes the process itself stays up (e.g. via a terminal left open, a Windows service, or Task Scheduler).

### Frontend

```bash
cd frontend
flutter pub get
flutter run -d chrome    # or: flutter run -d windows
```

The Flutter app always talks to `127.0.0.1:9000` — it only works while the backend above is running locally. It's a dashboard/config UI, not required for the bot itself to function (see below).

## Deploying: GitHub Actions as the always-on runner

Running the FastAPI app locally (previous section) means the bot only polls while your machine is on. `.github/workflows/ingest.yml` avoids that entirely: a scheduled GitHub Actions workflow runs one ingestion pass every hour on GitHub's infrastructure, with no server of your own required. State (seen jobs, ingestion settings, saved keywords) lives in `backend/job_alert.db`, which the workflow commits back to the repo after every run — this is why `job_alert.db` is intentionally tracked in git rather than ignored.

### One-time setup

1. **Add repository secrets** (Settings → Secrets and variables → Actions → New repository secret) — same names as the `.env` variables, added one at a time since there's no way to bulk-import from a script:
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (required for alerts)
   - `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD` (if using LinkedIn/Naukri email alerts)
   - Optionally: `ALERT_EMAIL_IMAP_HOST`, `ALERT_EMAIL_IMAP_PORT`, `LINKEDIN_ALERT_SENDER`, `NAUKRI_ALERT_SENDER`, `WEWORKREMOTELY_FEED_URL`, `HIMALAYAS_FEED_URL`, `UNSTOP_FEED_URL`, `FOUNDIT_FEED_URL`
2. **Allow the workflow to push**: Settings → Actions → General → Workflow permissions → "Read and write permissions". Without this, the DB commit-back step fails (the ingestion itself still runs fine, but state won't persist between runs).
3. **Enable/tune settings and keywords once**, either by editing `backend/job_alert.db` via a local run (see below) or by running the local backend, changing things through the Flutter app or API, then committing the resulting `job_alert.db`.
4. Trigger it once manually via the **Actions** tab → "Scheduled ingestion" → "Run workflow" to confirm it works before waiting for the first scheduled run.

### Don't run both at once

The local FastAPI scheduler and the GitHub Actions cron runner each operate on their own copy of `job_alert.db` — they don't share state in real time, only whenever you `git pull`/`git push`. If you leave the local server running continuously *and* have the Actions workflow enabled, both will independently detect the same new postings and **you'll get duplicate Telegram alerts**. Pick one as the primary runner:

- **Actions as primary (recommended, matches "no laptop dependency")**: don't leave the local backend running unattended. Use it only for occasional dashboard/config sessions — `git pull` first, make your changes, `git push` after, so the next scheduled run picks them up.
- **Local as primary**: keep the Actions workflow disabled (Actions tab → "Scheduled ingestion" → "···" → Disable workflow), and run the FastAPI backend continuously instead (previous section).

## Testing

Backend (pytest, no live network calls — safe to run anywhere, including CI):

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Covers `matcher_service`, `dedup_service`, `email_parsers` (against hand-built sample HTML), and repository-level duplicate/conflict handling (`job_repository`, `preference_repository`, `ingestion_settings_repository`) against a temp SQLite DB.

Frontend:

```bash
cd frontend
flutter analyze
flutter test
```

## CI/CD

Two separate workflows, deliberately not combined:

- **`.github/workflows/ci.yml`** — runs on every push/PR to `main`. Backend job installs `requirements.txt`, byte-compiles the app (`python -m compileall`), runs `pytest -q`. Frontend job runs `flutter pub get`, `flutter analyze`, `flutter test`. Self-contained — no secrets, no live network calls required to pass. A red run means an actual regression. Commits made by the ingestion workflow include `[skip ci]` so a routine DB update doesn't re-trigger the whole test suite.
- **`.github/workflows/ingest.yml`** — the scheduled cron runner described above. Needs the repository secrets and write permissions set up once (see "Deploying").

## Notes

- The backend listens on `http://127.0.0.1:9000`; the frontend targets the same.
- `POST /ingest` (also triggered by the Flutter "Check for new jobs now" button) is a manual on-demand run of the exact same pipeline the scheduler runs automatically — safe to call anytime, including while a scheduled run might be in flight, since dedup is atomic at the database layer.
- `CORS` is wide open (`allow_origins=["*"]`) for local development; tighten before exposing this beyond `127.0.0.1`.
- `preferences.location` is stored but not yet used in matching.
