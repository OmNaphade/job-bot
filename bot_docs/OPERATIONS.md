# Running, deploying, and testing

## Running locally

### Backend

The database is Postgres (with the pgvector extension), not a local file anymore. For local dev, `docker compose` starts a throwaway Postgres+pgvector container matching `.env.example`'s default `DATABASE_URL`:

```bash
cd backend
docker compose up -d          # starts Postgres+pgvector on localhost:5433
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
REM edit .env with real values, then:
python -m alembic upgrade head   # applies schema -- required before first run
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

Schema changes live in `backend/alembic/versions/` and are applied explicitly (`alembic upgrade head`), not automatically on app startup — see `bot_docs/ARCHITECTURE.md`'s "Database and migrations."

Running `uvicorn main:app` only serves the API — it no longer runs ingestion itself (there used to be an in-process scheduler; it's gone, see "Deploying to OCI" below for why). To run an ingestion pass locally, either call `POST /ingest` (this account only, immediately) from the app/API, or run `python -m scripts.run_ingestion_once` (every due account) directly in another terminal.

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

Two caveats specific to phones, already handled but worth knowing about: the backend is plain HTTP with no TLS, so Android (`usesCleartextTraffic`) and iOS (`NSAllowsLocalNetworking`) both need explicit opt-in to allow it — already configured in this project's manifests, scoped to local-network traffic rather than allowing arbitrary HTTP everywhere. This only works while your PC and the backend process are actually running and reachable — it does not replace the always-on OCI deployment (see "Deploying to OCI" below); it's for checking the dashboard and tweaking settings from your phone while your PC happens to be up, or for pointing the app at your deployed VM1 instead of localhost.

Binding to `0.0.0.0` means the API is reachable by anything on the same network, not just your phone. Every endpoint except `/health` and `/auth/*` requires a real per-user login (see "Accounts and multi-user" below) — set `SIGNUP_INVITE_CODE` in `backend/.env` (see `.env.example`) if you also want to stop a stranger on the same network from creating an account of their own; unset (the default) leaves signup open to anyone who can reach the URL.

## Accounts and multi-user

Every user of a given deployment signs up their own account (email + password, `POST /auth/signup` or the app's **Create account** screen) and gets their own independently-scoped keyword filters, ingestion source toggles, notification channels (Telegram/Slack/Discord), and job history — none of that is shared between accounts, even though they're all backed by the same Postgres database.

- **Signup gate**: if `SIGNUP_INVITE_CODE` is set in `backend/.env`, signup requires that value in the invite-code field; unset (the default) means anyone who can reach the backend URL can create an account. This is the only thing `SIGNUP_INVITE_CODE` gates — once logged in, every user has the same access to their own data.
- **Sessions**: logging in returns a bearer token (`Authorization: Bearer <token>`), stored by the Flutter app and sent on every request. Tokens last `SESSION_TTL_DAYS` (30 by default) and can be revoked early via **Settings → Log out**, which deletes the session server-side.
- **Notification channels are per-account**: set your own Telegram bot token/chat ID and/or Slack/Discord webhook URLs from **Settings → Notifications** in the app (or `PUT /notification-settings`) — these used to be global `.env` variables (`TELEGRAM_BOT_TOKEN` etc.) in earlier versions of this project; they're per-user DB rows now, so each account's alerts go to that account's own channels.
- **Ingestion runs once per user, not once globally**: `scripts/run_ingestion_once.py` (run every 15 minutes by VM2's `job-alert-worker.timer` in production — see "Deploying to OCI" below) calls `IngestionService.run_all_users()`, which loops every account and skips anyone not yet due per their own `poll_interval_hours`. A manual **Check for new jobs now** in the app (`POST /ingest`) only runs your own account's pass, immediately, regardless of whether you're "due."
- **Adapter-level config stays global**: the actual data-source credentials/queries (RSS feed URLs, Adzuna/Jooble/The Muse API keys, Foundit/Greenhouse/Lever/Ashby board tokens, the shared alert-email mailbox) are still `backend/.env`-configured, shared by the whole deployment — per-account scoping only applies to which of those *enabled* sources a given user wants matched against their own keywords, and where their own alerts go.

### Migrating from the legacy SQLite deployment

Deployments that predate the Postgres cutover have their state in `backend/job_alert.db` (no longer read by the app at all). `backend/scripts/migrate_sqlite_to_postgres.py` copies every table across, preserving IDs/relationships, into whatever `DATABASE_URL` currently points at — see the script's docstring for usage and the row-count verification it prints. Run it once, after `alembic upgrade head` has created the schema and before pointing real traffic at Postgres.

### Upgrading an existing single-user install

If you're upgrading a deployment that predates accounts (its `jobs`/`preferences`/`ingestion_settings` rows have no owner), those old rows aren't automatically claimed by any new account — there's no way to know at migration time which future account should own them. After signing up your own account for the first time:

1. Find your new user id: `psql "$DATABASE_URL" -c "SELECT id, email FROM users;"` (or query it via any DB browser).
2. Reassign the old, ownerless rows to it:
   ```sql
   UPDATE jobs SET user_id = <your_id> WHERE user_id IS NULL;
   UPDATE preferences SET user_id = <your_id> WHERE user_id IS NULL;
   ```
3. Re-enable your ingestion sources and re-enter your notification channels once through the app — the old singleton `ingestion_settings` row and any `.env`-configured Telegram token aren't carried forward automatically; this is a few minutes of one-time setup, not a repeating chore.

## Deploying to OCI (2 VMs)

The app runs on two small always-free OCI VMs in the same VCN, reaching each other over private IPs only:

- **VM1 (app)** — nginx (TLS via Let's Encrypt/certbot, serves the Flutter web build, reverse-proxies `/api/`) + the FastAPI backend (`job-alert.service`, systemd). Provisioned by `deploy/oci_deploy_app.sh`.
- **VM2 (db/worker)** — Postgres+pgvector (reachable only from VM1's private IP — never the public internet) + `job-alert-worker.timer`, a systemd timer that runs one ingestion+matching pass every 15 minutes. This is the **only** place ingestion is scheduled — there is no in-process scheduler in the app anymore, and no GitHub Actions cron; both were retired in favor of this single mechanism (see `bot_docs/ARCHITECTURE.md`). Provisioned by `deploy/oci_deploy_db.sh`, which also owns running Alembic migrations (`alembic upgrade head`) — VM1's script never touches schema, so the two VMs can't race a migration against each other.

### One-time setup

1. **Stand up VM2 first** (nothing on VM1 can reach a database that doesn't exist yet):

   ```bash
   ssh <vm2>
   git clone https://github.com/OmNaphade/job-bot.git ~/job-bot
   cd ~/job-bot/deploy
   DB_PASSWORD='<a real generated password>' APP_HOST=<VM1's private IP> ./oci_deploy_db.sh
   ```

   Then edit `~/job-bot/backend/.env` on VM2 to fill in `GOOGLE_API_KEY` and whichever ingestion-source secrets you want enabled (`ALERT_EMAIL_*`, `ADZUNA_*`, `GREENHOUSE_BOARD_TOKENS`, etc. — see [SOURCES.md](SOURCES.md)), then `sudo systemctl restart job-alert-worker.timer`.
2. **If you want a real domain**, claim a free subdomain at [duckdns.org](https://www.duckdns.org) pointing at VM1's public IP, and note the token.
3. **Stand up VM1**:

   ```bash
   ssh <vm1>
   git clone https://github.com/OmNaphade/job-bot.git ~/job-bot
   cd ~/job-bot/deploy
   SERVER_NAME=your-subdomain.duckdns.org \
   LETSENCRYPT_EMAIL=you@example.com \
   DUCKDNS_TOKEN='...' DUCKDNS_SUBDOMAIN=your-subdomain \
   ./oci_deploy_app.sh
   ```

   Then edit `~/job-bot/backend/.env` on VM1: set `DATABASE_URL` to VM2's *private* IP (never the public one), `GOOGLE_API_KEY`, and `ALLOWED_ORIGIN` to `https://your-subdomain.duckdns.org` (see `.env.example`), then `sudo systemctl restart job-alert`.
4. **Build and publish the Flutter web frontend**: `flutter build web` locally, `scp -r build/web/* <vm1>:~/web-build/`, then re-run `oci_deploy_app.sh` on VM1 to publish it.
5. **Sign up your first account** through the deployed web app, confirm a manual ingestion pass works (`sudo systemctl start job-alert-worker.service && sudo journalctl -u job-alert-worker.service -n 50` on VM2), and confirm the timer is enabled (`systemctl status job-alert-worker.timer`).
6. **If you migrated from the legacy SQLite deployment**, jobs that existed before this cutover have no embedding yet (they were never re-ingested through the new pipeline) and won't show up in `GET /matches` until backfilled. On VM2: `cd ~/job-bot/backend && .venv/bin/python -m scripts.backfill_job_embeddings`. Safe to re-run; it only processes jobs still missing an embedding.

Both scripts are safe to re-run any time after a `git push` — they pull the latest code, reinstall dependencies, and restart the relevant service(s) without touching `.env` or (on VM1) an already-certbot-edited nginx config.

### Run history / logs

Every run — success or failure, scheduled or manual — is recorded as a row in the `ingestion_runs` table in Postgres. Two ways to see it:

- **`GET /ingestion/runs`** — query the persisted history (timestamps, counts, error message if it failed) from the API/Flutter app.
- **`sudo journalctl -u job-alert-worker.service -n 100`** on VM2 — the raw application log for the most recent tick(s), including the per-source fetched/matched breakdown that `IngestionService.run()` logs (see `bot_docs/ARCHITECTURE.md`'s "Per-source visibility") — this is the place to check when a source seems to be contributing nothing, before assuming it's broken.
- **`systemctl list-timers job-alert-worker.timer`** — confirms the timer is actually scheduled and shows when it last/next fires.

## Testing

Backend (pytest, no live network calls — safe to run anywhere, including CI). Needs a running Postgres+pgvector instance (`docker compose up -d` in `backend/`, or point `TEST_DATABASE_URL` at another one):

```bash
cd backend
docker compose up -d
pip install -r requirements.txt
pytest -q
```

Covers `matcher_service` (including location-scoped keyword filters), `dedup_service`, `notification_service` (Telegram/Slack/Discord digest chunking and partial-failure delivery tracking, per-user `NotificationSettings`), `auth_service`/`security` (signup/login/logout, password hashing, session validation), `scheduler` (fixed-tick wiring), `ingestion_service` (`run_for_user`/`run_all_users`, per-user due-check), the API routes (`app/api/routes.py`, via FastAPI's `TestClient`), `safe_registry` (adapter construction from settings/env, including CSV-token and `allow_direct_scraping` gating), `email_parsers` (against hand-built sample HTML), the RSS/RemoteOK/ATS adapters, and repository-level duplicate/conflict and cross-user-isolation handling (`job_repository`, `preference_repository`, `ingestion_settings_repository`, `ingestion_run_repository`, `user_repository`, `session_repository`, `notification_settings_repository`).

Test isolation runs each test inside its own outer Postgres transaction, rolled back at teardown (see `backend/tests/conftest.py`) — Alembic migrations run once per test session against a dedicated `job_alert_test` database (created automatically by `docker-compose.yml`), not once per test.

Frontend:

```bash
cd frontend
flutter analyze
flutter test
```

## CI/CD

- **`.github/workflows/ci.yml`** — runs on every push/PR to `main`. Backend job spins up a `pgvector/pgvector:pg16` service container, installs `requirements.txt` (the version *ranges*, deliberately — a red run here is the earliest signal that a new release inside an allowed range broke something, and a human is watching this run), byte-compiles the app (`python -m compileall`), runs `pytest -q` against the service container (`TEST_DATABASE_URL`, see `backend/tests/conftest.py`). Frontend job runs `flutter pub get`, `flutter analyze`, `flutter test`.
- There is no scheduled workflow anymore — ingestion runs on VM2's `job-alert-worker.timer` in production (see "Deploying to OCI" above), not via GitHub Actions. `backend/requirements-lock.txt` (exact pinned versions) is what `deploy/oci_deploy_db.sh` installs on VM2, for the same reason it was previously used by the retired scheduled workflow: nobody is watching that install run every 15 minutes, so it gets the known-good pinned set rather than whatever the `requirements.txt` ranges resolve to that day. Regenerate it deliberately (see the header comment in `requirements-lock.txt`) after confirming the new versions pass `pytest -q`, not automatically.
