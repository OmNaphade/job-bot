# Running, deploying, and testing

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

The scheduler starts automatically with the app — as long as this process is running, it ticks every 15 minutes and runs an ingestion pass for each user who's actually due, per their own `poll_interval_hours` (see "Accounts and multi-user" below). This assumes the process itself stays up (e.g. via a terminal left open, a Windows service, or Task Scheduler).

### Frontend

```bash
cd frontend
flutter pub get
flutter run -d chrome    # or: flutter run -d windows
```

It's a dashboard/config UI, not required for the bot itself to function (see below).

By default the app targets `127.0.0.1:9000` (`10.0.2.2:9000` on the Android emulator, which is the emulator's alias for the host machine's loopback). This is overridden per-device from **Server Connection** (the 🖥 icon in the app bar, or offered directly from the "couldn't reach the backend" error screen) and persisted with `shared_preferences`, so it survives app restarts.

#### Running on a phone (Android/iOS)

`127.0.0.1` on a phone means the phone itself, not your PC — a real device needs your PC's actual LAN IP:

1. Start the backend bound to all interfaces, not just loopback: `uvicorn main:app --host 0.0.0.0 --port 9000`.
2. Find your PC's LAN IP: `ipconfig` on Windows (the IPv4 address, e.g. `192.168.1.42`) — phone and PC must be on the same Wi-Fi network.
3. Allow inbound connections on port 9000 through Windows Firewall if prompted (or add a rule manually: Windows Defender Firewall → Advanced settings → Inbound Rules).
4. Build/run the app on the device (`flutter run` with a device attached and USB debugging enabled, or `flutter build apk` and install the APK). Android platform support requires the Android SDK (Android Studio) to be installed; iOS builds require Xcode on macOS.
5. In the app, open **Server Connection**, enter `http://192.168.1.42:9000` (your actual IP), tap **Test connection**, then **Save**. Then sign up or log in with your account — the login screen is what the app opens to by default.

Two caveats specific to phones, already handled but worth knowing about: the backend is plain HTTP with no TLS, so Android (`usesCleartextTraffic`) and iOS (`NSAllowsLocalNetworking`) both need explicit opt-in to allow it — already configured in this project's manifests, scoped to local-network traffic rather than allowing arbitrary HTTP everywhere. This only works while your PC and the backend process are actually running and reachable — it does not replace the GitHub Actions scheduled runner as the always-on path (see below); it's for checking the dashboard and tweaking settings from your phone while your PC happens to be up.

Binding to `0.0.0.0` means the API is reachable by anything on the same network, not just your phone. Every endpoint except `/health` and `/auth/*` requires a real per-user login (see "Accounts and multi-user" below) — set `SIGNUP_INVITE_CODE` in `backend/.env` (see `.env.example`) if you also want to stop a stranger on the same network from creating an account of their own; unset (the default) leaves signup open to anyone who can reach the URL.

## Accounts and multi-user

Every user of a given deployment signs up their own account (email + password, `POST /auth/signup` or the app's **Create account** screen) and gets their own independently-scoped keyword filters, ingestion source toggles, notification channels (Telegram/Slack/Discord), and job history — none of that is shared between accounts, even though they're all backed by the same `job_alert.db`.

- **Signup gate**: if `SIGNUP_INVITE_CODE` is set in `backend/.env`, signup requires that value in the invite-code field; unset (the default) means anyone who can reach the backend URL can create an account. This is the only thing `SIGNUP_INVITE_CODE` gates — once logged in, every user has the same access to their own data.
- **Sessions**: logging in returns a bearer token (`Authorization: Bearer <token>`), stored by the Flutter app and sent on every request. Tokens last `SESSION_TTL_DAYS` (30 by default) and can be revoked early via **Settings → Log out**, which deletes the session server-side.
- **Notification channels are per-account**: set your own Telegram bot token/chat ID and/or Slack/Discord webhook URLs from **Settings → Notifications** in the app (or `PUT /notification-settings`) — these used to be global `.env` variables (`TELEGRAM_BOT_TOKEN` etc.) in earlier versions of this project; they're per-user DB rows now, so each account's alerts go to that account's own channels.
- **Ingestion runs once per user, not once globally**: the scheduler (local always-on backend) and the GitHub Actions runner (`scripts/run_ingestion_once.py`) both call `IngestionService.run_all_users()`, which loops every account and skips anyone not yet due per their own `poll_interval_hours`. A manual **Check for new jobs now** in the app (`POST /ingest`) only runs your own account's pass, immediately, regardless of whether you're "due."
- **Adapter-level config stays global**: the actual data-source credentials/queries (RSS feed URLs, Adzuna/Jooble/The Muse API keys, Foundit/Greenhouse/Lever/Ashby board tokens, the shared alert-email mailbox) are still `backend/.env`/GitHub-secret configured, shared by the whole deployment — per-account scoping only applies to which of those *enabled* sources a given user wants matched against their own keywords, and where their own alerts go.

### Upgrading an existing single-user install

If you're upgrading a deployment that predates accounts (its `jobs`/`preferences`/`ingestion_settings` rows have no owner), those old rows aren't automatically claimed by any new account — there's no way to know at migration time which future account should own them. After signing up your own account for the first time:

1. Find your new user id: `sqlite3 backend/job_alert.db "SELECT id, email FROM users;"` (or query it via any DB browser).
2. Reassign the old, ownerless rows to it:
   ```sql
   UPDATE jobs SET user_id = <your_id> WHERE user_id IS NULL;
   UPDATE preferences SET user_id = <your_id> WHERE user_id IS NULL;
   ```
3. Re-enable your ingestion sources and re-enter your notification channels once through the app — the old singleton `ingestion_settings` row and any `.env`-configured Telegram token aren't carried forward automatically (see the migration comments in `backend/app/db/database.py` for why); this is a few minutes of one-time setup, not a repeating chore.

## Deploying: GitHub Actions as the always-on runner

Running the FastAPI app locally means the bot only polls while your machine is on. `.github/workflows/ingest.yml` avoids that entirely: a scheduled GitHub Actions workflow runs one ingestion pass every hour (`cron: "17 * * * *"`, 24 runs/day — offset from the top of the hour to dodge the peak-load congestion GitHub sees at `:00`) on GitHub's infrastructure, with no server of your own required. State (seen jobs, ingestion settings, saved keywords, run history) lives in `backend/job_alert.db`, which the workflow commits back to the repo after every run — this is why `job_alert.db` is intentionally tracked in git rather than ignored.

The schedule runs entirely on GitHub's servers — it's unaffected by whether any of your own devices are online.

Two caveats:
- GitHub doesn't guarantee exact cron timing under load — in practice, runs have landed anywhere from a few minutes to ~45 minutes after the target minute, and occasionally an hour gets skipped entirely; there's no backfill. This is a known limitation of GitHub's free scheduled Actions, not a misconfiguration here — and it's low-stakes for this bot specifically, since dedup is atomic at the database layer (`jobs.link UNIQUE`), so a late or skipped run only delays an alert, it never loses or duplicates one.
- GitHub auto-disables scheduled workflows after 60 days with zero commits to the repo. An active job hunt keeps this alive naturally (matches get committed), but if it goes fully quiet for 60 days the schedule stops until a commit or manual re-enable.

If the repo is ever made **private**, note that Actions minutes stop being unlimited-free and start counting against the account's monthly quota (2,000 min/month on GitHub's Free plan) — check actual run duration in the Actions tab before switching visibility.

### One-time setup

1. **Add repository secrets** (Settings → Secrets and variables → Actions → New repository secret) — same names as the `.env` variables (see [SOURCES.md](SOURCES.md)), added one at a time since there's no way to bulk-import from a script. Notification channels (Telegram/Slack/Discord) are **not** repository secrets anymore — they're per-account, set through the app. What's still env/secret-configured is the shared, deployment-wide adapter config:
   - `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD` (if using LinkedIn/Naukri/Indeed email alerts)
   - Optionally: `ALERT_EMAIL_IMAP_HOST`, `ALERT_EMAIL_IMAP_PORT`, `LINKEDIN_ALERT_SENDER`, `NAUKRI_ALERT_SENDER`, any of the RSS/JSON feed URL overrides, the Tier-A aggregator API keys, and `GREENHOUSE_BOARD_TOKENS`/`LEVER_COMPANY_SLUGS`/`ASHBY_BOARD_NAMES` (also needs `allow_direct_scraping` turned on per-account — see [SOURCES.md](SOURCES.md))
   - `SIGNUP_INVITE_CODE` if you want to gate who can create an account against this deployment
2. **Allow the workflow to push**: Settings → Actions → General → Workflow permissions → "Read and write permissions". Without this, the DB commit-back step fails (the ingestion itself still runs fine, but state won't persist between runs).
3. **Sign up an account and tune settings/keywords/notifications once**, either by running the local backend and using the Flutter app, or via the API directly, then committing the resulting `job_alert.db`.
4. Trigger it once manually via the **Actions** tab → "Scheduled ingestion" → "Run workflow" to confirm it works before waiting for the first scheduled run.

### Run history / logs

Every run — success or failure, scheduled or manual — is recorded as a row in the `ingestion_runs` table, which lives in `job_alert.db` and gets committed back to the repo like everything else. Two ways to see it:

- **`GET /ingestion/runs`** — query the persisted history (timestamps, counts, error message if it failed) from the API/Flutter app. This only holds the aggregate counts (`fetched_count`, `matched_count`, etc.), not a per-source breakdown.
- **GitHub Actions run summary** — each scheduled run also writes a short markdown summary directly to that run's page under the **Actions** tab, no DB query needed. Click into any past run → the "Summary" tab. Beyond the aggregate fetched/matched/new/delivered counts, it includes a **per-source table** (fetched and matched count for every individual source that run) — this is the place to check when a source seems to be contributing nothing, before assuming it's broken.
- **Application logs** — every source logs its own outcome at INFO level (`Source 'X': checked, fetched N candidate(s)`, or a WARNING/exception if it failed) via `SafeAdapterRegistry.fetch_all()`; the aggregate + per-source breakdown is logged again by `IngestionService.run()`. Visible in the raw step log for a scheduled run, or directly in the console for a local run.

The commit-back step runs even when ingestion itself fails (`if: always()` in `ingest.yml`), so a failed run's history is pushed to the repo too, not just successful ones — and the workflow step itself still exits non-zero on failure, which is what drives GitHub's own "workflow run failed" email notification to repo watchers.

### Don't run both at once

The local FastAPI scheduler and the GitHub Actions cron runner each operate on their own copy of `job_alert.db` — they don't share state in real time, only whenever you `git pull`/`git push`. If you leave the local server running continuously *and* have the Actions workflow enabled, both will independently run ingestion for every account and **you'll get duplicate alerts** on whichever channels each account has configured. Pick one as the primary runner:

- **Actions as primary (recommended, matches "no laptop dependency")**: don't leave the local backend running unattended. Use it only for occasional dashboard/config sessions — `git pull` first, make your changes, `git push` after, so the next scheduled run picks them up.
- **Local as primary**: keep the Actions workflow disabled (Actions tab → "Scheduled ingestion" → "···" → Disable workflow), and run the FastAPI backend continuously instead.

## Testing

Backend (pytest, no live network calls — safe to run anywhere, including CI):

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Covers `matcher_service` (including location-scoped keyword filters), `dedup_service`, `notification_service` (Telegram/Slack/Discord digest chunking and partial-failure delivery tracking, per-user `NotificationSettings`), `auth_service`/`security` (signup/login/logout, password hashing, session validation), `scheduler` (fixed-tick wiring), `ingestion_service` (`run_for_user`/`run_all_users`, per-user due-check), the API routes (`app/api/routes.py`, via FastAPI's `TestClient`), `safe_registry` (adapter construction from settings/env, including CSV-token and `allow_direct_scraping` gating), `email_parsers` (against hand-built sample HTML), the RSS/RemoteOK/ATS adapters, and repository-level duplicate/conflict and cross-user-isolation handling (`job_repository`, `preference_repository`, `ingestion_settings_repository`, `ingestion_run_repository`, `user_repository`, `session_repository`, `notification_settings_repository`) against a temp SQLite DB.

Frontend:

```bash
cd frontend
flutter analyze
flutter test
```

## CI/CD

Two separate workflows, deliberately not combined:

- **`.github/workflows/ci.yml`** — runs on every push/PR to `main`. Backend job installs `requirements.txt` (the version *ranges*, deliberately — a red run here is the earliest signal that a new release inside an allowed range broke something, and a human is watching this run), byte-compiles the app (`python -m compileall`), runs `pytest -q`. Frontend job runs `flutter pub get`, `flutter analyze`, `flutter test`. Self-contained — no secrets, no live network calls required to pass. Commits made by the ingestion workflow include `[skip ci]` so a routine DB update doesn't re-trigger the whole test suite.
- **`.github/workflows/ingest.yml`** — the scheduled cron runner described above. Installs from `backend/requirements-lock.txt` (exact pinned versions, not ranges) instead — nobody is watching this run every hour, so it gets the known-good pinned set rather than whatever the ranges resolve to that day. Regenerate the lock file deliberately (see the header comment in `requirements-lock.txt`) after confirming the new versions pass `pytest -q`, not automatically. Needs the repository secrets and write permissions set up once (see "One-time setup").
