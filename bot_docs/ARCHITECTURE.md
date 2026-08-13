# Architecture

## Overview

The application has three main layers, and is multi-user: every account (email+password, see "Accounts" below) gets its own independently-scoped keyword preferences, ingestion source toggles, notification channels, and job history, all backed by one shared `job_alert.db`.

- **Backend API**: FastAPI service exposing auth (signup/login/logout), job, preference, ingestion-settings, notification-settings, and ingestion endpoints — every one of them (except `/health` and the two auth-entry routes) scoped to whichever account the request's session token belongs to.
- **Ingestion pipeline**: a background scheduler ticks frequently and runs the same pipeline the API exposes manually, once per account that's actually due for a check — fetch candidate jobs from that account's enabled sources, match them against that account's saved keywords, deduplicate against that account's previously-seen jobs, persist new ones, and send a digest to that account's configured channels (Telegram/Slack/Discord).
- **Frontend UI**: a Flutter dashboard, gated behind a login screen, that displays the logged-in account's stored jobs, lets you trigger an on-demand check, and configures sources/keywords/notifications for that account. It's a secondary control panel — the backend keeps running and alerting on its own schedule whether or not the app is open.

### Accounts

`users`/`sessions` tables back email+password login (bcrypt-hashed passwords, opaque bearer session tokens — see `backend/app/core/security.py`). Signup can optionally require an invite code (`SIGNUP_INVITE_CODE`). See `bot_docs/OPERATIONS.md`'s "Accounts and multi-user" section for the operational side of this (setup, upgrading a pre-accounts install, what stays global vs. per-account).

## Backend

- `backend/main.py`
  - FastAPI application bootstrap with a `lifespan` hook: initializes the database and starts the background scheduler on startup, stops the scheduler on shutdown.
  - Registers CORS middleware and the API router.
- `backend/app/api/routes.py`
  - HTTP endpoints for auth, jobs, preferences, ingestion settings, notification settings, ingestion, and ingestion run history. Services are wired in via FastAPI `Depends`; every protected handler also depends on `get_current_user` and passes `current_user.id` down.
- `backend/app/services/`
  - `auth_service.py`: signup/login/logout.
  - `job_service.py` / `preference_service.py` / `ingestion_settings_service.py` / `ingestion_run_service.py` / `notification_settings_service.py`: business logic, one service per entity, each method taking a `user_id`.
  - `errors.py`: `DuplicateResourceError` (uniqueness conflict → `HTTPException(409)`), `InvalidCredentialsError` (bad login/invite code → 401/403). Both raised by repositories/services and translated in routes.
- `backend/app/repositories/`
  - `user_repository.py` / `session_repository.py`: accounts and login sessions.
  - `job_repository.py` / `preference_repository.py` / `ingestion_settings_repository.py` / `ingestion_run_repository.py` / `notification_settings_repository.py`: SQLite persistence, one repository per entity, every query scoped by `user_id`.
- `backend/app/db/database.py`
  - `init_db()`: creates all tables once at startup (not per-request), then runs a fixed sequence of migration functions — mostly additive `ALTER TABLE ADD COLUMN`, but a few (adding `user_id` to `jobs`/`preferences`) needed a full table rebuild since SQLite can't alter a `UNIQUE` constraint in place.
  - `db_session()`: a context manager that commits on success, rolls back on error, and always closes the connection.
- `backend/app/ingestion/`
  - `scheduler.py`: wraps an APScheduler `BackgroundScheduler` that ticks on a fixed 15-minute interval and calls `IngestionService.run_all_users()` each time — per-user cadence is decided inside that call (see `IngestionService._is_due`), not by the scheduler's own interval.
  - `services/ingestion_service.py`: `run_for_user(user_id)` orchestrates one account's ingestion run — build the adapter registry from that account's settings, build the matcher from their keyword preferences, fetch, match, dedup, persist, notify via their `NotificationSettings`, and record the outcome to `ingestion_runs`. `run_all_users()` loops every account, skipping anyone not yet due.
  - `services/matcher_service.py`: include/exclude keyword matching against title/company/location.
  - `services/dedup_service.py`: in-batch dedup (catches two adapters returning the same link in one run). Cross-run dedup is handled atomically at the DB layer via `jobs.link UNIQUE` + `INSERT OR IGNORE`.
  - `services/notification_service.py`: sends a digest to every channel (Telegram/Slack/Discord) a given user has configured (`NotificationSettings`, per-user, see `notification_settings_repository.py`), for jobs pending delivery (`JobRepository.list_unnotified(user_id)` -- this run's new matches plus any left over from a run whose send failed partway through, bounded at 200 oldest-first per run so a multi-day outage doesn't try to flush an ever-growing backlog in one go), and returns the ids delivered to at least one channel. `IngestionService.run_for_user()` marks only those ids `notified_at` via `JobRepository.mark_notified()`, so an outage delays delivery rather than losing it -- persistence (which drives dedup) and delivery are decoupled.
  - `adapters/rss_adapter.py`: fetches and parses a configured RSS/Atom feed (most Tier A sources).
  - `adapters/remoteok_adapter.py`: fetches RemoteOK's JSON API (its RSS feed was discontinued) — a dedicated adapter since the payload isn't RSS/Atom.
  - `adapters/ats_adapters.py`: `GreenhouseAdapter`/`LeverAdapter`/`AshbyAdapter` — pull postings directly from a company's public ATS job-board API (Tier C, gated by `allow_direct_scraping`, not `enable_rss_sources`). One instance per configured board token, registered dynamically from the comma-separated `GREENHOUSE_BOARD_TOKENS`/`LEVER_COMPANY_SLUGS`/`ASHBY_BOARD_NAMES` env vars — see [SOURCES.md](SOURCES.md).
  - `adapters/foundit_adapter.py`: `FounditAdapter` — pulls from Foundit's own internal (undocumented) search API, one instance per configured query term. Also gated by `allow_direct_scraping`. Uses a different User-Agent than the other adapters, since Foundit's edge keyword-blocks the literal substring "bot" — see [SOURCES.md](SOURCES.md) for the full rationale before touching this one.
  - `adapters/unstop_adapter.py`: `UnstopAdapter` — pulls from Unstop's own internal (undocumented) listing API. Also gated by `allow_direct_scraping`. No per-query configuration; fetches the latest open postings in bulk and relies on normal keyword matching, same as the RSS sources — see [SOURCES.md](SOURCES.md).
  - `adapters/email_adapter.py` + `adapters/email_parsers.py`: reads LinkedIn/Naukri/Indeed job-alert emails via IMAP and parses postings out of the HTML body (Tier B — never talks to linkedin.com/naukri.com/indeed.com directly). `EmailAdapter` searches every mailbox in a configured list (INBOX plus, optionally, a Gmail label folder), bounded to the last `LOOKBACK_DAYS` (3) days via IMAP's `SINCE` — see [SOURCES.md](SOURCES.md). LinkedIn's and Indeed's parsers are validated against real alert emails; Naukri's is still best-effort (no real job-digest sample has been available to check it against). Deliberately does not rely on IMAP's `\Seen`/`UNSEEN` flag to decide what's new -- see `ProcessedAlertEmailRepository` below.
  - `repositories/processed_alert_email_repository.py`: tracks which alert-email Message-IDs `EmailAdapter` has already turned into candidates, independent of the mailbox's own read state (a Gmail filter with "mark as read" as one of its actions, or the user simply reading their own mail, previously made an IMAP `UNSEEN` search silently skip real alerts forever — see [SOURCES.md](SOURCES.md)).
- `backend/app/core/config.py`
  - Static, deployment-wide configuration read from environment variables (IMAP credentials, alert sender addresses, feed URLs, adapter API keys, optional `SIGNUP_INVITE_CODE`). Per-user data (notification channels, keyword preferences, ingestion toggles) lives in the DB instead, not here.
- `backend/app/core/security.py`
  - `hash_password`/`verify_password`: bcrypt-backed password hashing.
  - `get_current_user`: resolves `Authorization: Bearer <token>` to a `User` via `SessionRepository` + `UserRepository`, 401s on missing/invalid/expired. Applied to every route except `/health`, `/auth/signup`, and `/auth/login` (see `routes.py`'s `protected` sub-router). Replaced the older `require_api_key` shared-secret gate once real per-user accounts existed — see `bot_docs/OPERATIONS.md`'s "Accounts and multi-user" section.
- `backend/app/services/auth_service.py`
  - `AuthService.signup`/`login`/`logout` — signup optionally checks `SIGNUP_INVITE_CODE` (constant-time compare), both signup and login create a session token (`SessionRepository.create`, 30-day default expiry), logout deletes it.
- `backend/scripts/run_ingestion_once.py`
  - Short-lived entrypoint for a single multi-user ingestion pass (`IngestionService.run_all_users()`) — what the GitHub Actions scheduled workflow actually runs, as opposed to the long-running `main.py` + APScheduler used for local/always-on operation. Also writes a per-user run summary to the GitHub Actions step summary when running in CI.

## Frontend

- `frontend/lib/main.dart` — app entry point; awaits `ApiService.instance.init()` (loads the persisted backend URL) and `AuthService.instance.init()` (loads any persisted session) before the first frame, sets up the "premium minimal dark SaaS" Material 3 theme (`theme/app_theme.dart`, light/dark), and roots the widget tree at `AuthGate` (below) instead of `HomeScreen` directly.
- `frontend/lib/main.dart`'s `AuthGate` — swaps between `LoginScreen` and `HomeScreen` based on `AuthService.instance.isLoggedIn`, listening to `AuthService` (a `ChangeNotifier`) so login/signup/logout/session-expiry all take effect immediately with no routing package involved.
- `frontend/lib/screens/login_screen.dart` / `signup_screen.dart` — email+password auth forms; signup has an optional invite-code field (only enforced if the backend has `SIGNUP_INVITE_CODE` set).
- `frontend/lib/screens/home_screen.dart` — dashboard showing stored jobs (source-colored cards with a company-logo avatar falling back to an initial, tap to copy the link) and an on-demand "Check for new jobs now" trigger. The unreachable-backend error state and the single settings AppBar icon both link to `SettingsHubScreen`.
- `frontend/lib/screens/settings_hub_screen.dart` — single settings home (replacing several separate AppBar icons): navigation to ingestion sources, keywords, notifications, server connection, run history, plus log out.
- `frontend/lib/screens/config_screen.dart` — loads/saves this account's ingestion source toggles and poll interval against the backend.
- `frontend/lib/screens/keyword_config_screen.dart` — loads this account's saved keywords and updates include/exclude filters.
- `frontend/lib/screens/notification_settings_screen.dart` — loads/saves this account's Telegram/Slack/Discord channel config (`GET`/`PUT /notification-settings`).
- `frontend/lib/screens/server_settings_screen.dart` — lets the user view/edit/test the backend base URL (needed on a real device, where `127.0.0.1` means the phone itself, not the PC running the backend — see [OPERATIONS.md](OPERATIONS.md#running-on-a-phone-androidios)). No longer has an API-key field — auth is per-account login now, not a shared secret.
- `frontend/lib/screens/run_history_screen.dart` — recent ingestion runs (status, timestamps, fetched/matched/new/delivered counts, error message on failure), backed by `GET /ingestion/runs`.
- `frontend/lib/services/api_service.dart` — the only place that talks HTTP to the backend; a singleton (`ApiService.instance`) so every screen shares one live base URL, with per-request timeouts. Every request carries `Authorization: Bearer <token>` when logged in; a 401 on an already-authenticated call triggers `AuthService.logout()` so an expired session drops back to the login screen instead of showing a generic error.
- `frontend/lib/services/auth_service.dart` — holds the current session token/email, persisted via `shared_preferences`; `signup`/`login`/`logout` wrap the matching `ApiService` calls and `notifyListeners()` so `AuthGate` reacts immediately.
- `frontend/lib/services/server_config.dart` — resolves the platform-appropriate default backend URL and persists the user's URL override via `shared_preferences`.
- `frontend/lib/theme/app_colors.dart` / `app_theme.dart` — the design-token system (dark-first color scheme, semantic success/warning colors via a `ThemeExtension`, per-source brand colors/labels) referenced by every screen instead of hardcoded literals.
- `frontend/lib/widgets/section_label.dart` — shared small section-header widget.
- `frontend/android/`, `frontend/ios/` — native platform scaffolding (added for mobile support). Android allows cleartext (plain HTTP) traffic and declares the `INTERNET` permission; iOS scopes `NSAllowsLocalNetworking` in `Info.plist` — both needed since the backend has no TLS and is only reachable on the local network.

## Data model and schema

### SQLite tables

- `users`
  - `id`, `email` (UNIQUE), `password_hash` (bcrypt), `created_at`.
- `sessions`
  - `token` (PRIMARY KEY, opaque `secrets.token_urlsafe(32)`), `user_id`, `created_at`, `expires_at` (30 days from creation by default, see `SESSION_TTL_DAYS`).
- `jobs`
  - `id`, `user_id`, `title`, `company`, `location`, `link`, `source`, `posted_at`, `logo_url`, `notified_at` (NULL until a digest containing this job is delivered to at least one of that user's configured channels; drives the per-user delivery retry queue, see `notification_service.py` above). `UNIQUE(user_id, link)` — the dedup key is scoped per user, not global, so two accounts who both match the same posting each get their own row. Jobs added manually via `POST /jobs` are stamped `notified_at` at creation so they don't get swept into the ingestion notification queue.
- `preferences`
  - `id`, `user_id`, `keyword`, `kind` (`include` or `exclude`), `location` (optional — scopes this keyword to only apply when the candidate's own `location` also matches it, e.g. exclude "manager" only for "New York"; `location=NULL` matches regardless, the common case); `UNIQUE(user_id, keyword, kind)`.
- `ingestion_settings`
  - One row per user (`user_id` PRIMARY KEY, created lazily on first access): `enable_rss_sources`, `enable_linkedin_alerts`, `enable_naukri_alerts`, `enable_indeed_alerts`, `allow_direct_scraping`, `poll_interval_hours`. Used to be a true singleton (`id = 1`) before multi-user accounts existed.
- `notification_settings`
  - One row per user (`user_id` PRIMARY KEY): `telegram_bot_token`, `telegram_chat_id`, `slack_webhook_url`, `discord_webhook_url` — all optional, all replacing what used to be global env vars.
- `processed_alert_emails`
  - `message_id`, `source`, `user_id`, `processed_at` -- `PRIMARY KEY (message_id, source, user_id)`. One row per alert email `EmailAdapter` has turned into candidates *for a given user*, keyed by the email's own Message-ID rather than the mailbox's `\Seen` flag (see the `adapters/email_adapter.py` bullet above and [SOURCES.md](SOURCES.md)). Scoped per user because the underlying mailbox is shared config — two accounts can both enable the same alert channel against it, and one account's pass marking a message processed must not hide it from another's.
- `ingestion_runs`
  - One row per per-user ingestion pass (manual or scheduled): `id`, `user_id`, `started_at`, `finished_at`, `status` (`success`/`failed`), `fetched_count`, `matched_count`, `new_count`, `delivered_count`, `error_message`. Written by `IngestionService.run_for_user()` itself, in both the success and failure path, so a crashed run is recorded too (see `GET /ingestion/runs`). Also what the scheduler consults (`most_recent_finished_at`) to decide if a user is due for another pass yet.

There is no separate "seen jobs" table — `jobs`'s `UNIQUE(user_id, link)`, combined with an atomic `INSERT OR IGNORE`, is the single dedup mechanism. Two of these tables (`jobs`, `preferences`) needed a SQLite table-rebuild migration rather than a plain `ALTER TABLE ADD COLUMN` when accounts were added, since SQLite can't alter an existing `UNIQUE` constraint — see the `_migrate_add_user_id_to_*` functions in `database.py` for the mechanics.

## Ingestion flow

`IngestionService.run_for_user(user_id)` is one pass for a single account:

1. Load that user's `ingestion_settings` and build the adapter registry — each adapter is enabled/disabled per its own toggle + (deployment-wide) feed URL/credentials.
2. Load that user's `preferences` (include/exclude keyword filters, each optionally scoped to a `location`) and build the matcher.
3. Fetch candidates from every enabled adapter (RSS/JSON sources + email-alert sources).
4. Match each candidate against the include/exclude keyword filters (whole-word match against title/company/location; a filter with a `location` set only applies when the candidate's location also matches it).
5. In-batch dedup (two adapters returning the same link in one run).
6. Persist: `INSERT OR IGNORE` per candidate — `jobs.UNIQUE(user_id, link)` silently drops anything already seen for this user in a prior run. Newly-persisted jobs start with `notified_at = NULL`.
7. Send a digest (to every channel in that user's `notification_settings`) for every job still pending delivery (`notified_at IS NULL`) — this run's new matches plus any left over from a run whose send failed partway through — and mark only the ones actually delivered.
8. Record the run outcome (counts, status, error if any) to `ingestion_runs`, scoped to that user.

`IngestionService.run_all_users()` — what the scheduler tick and `scripts/run_ingestion_once.py` actually call — loops every user, checks each one's `poll_interval_hours` against their own `most_recent_finished_at`, and calls `run_for_user` only for whoever is actually due. One user's failure doesn't stop the rest (already caught/logged/recorded inside `run_for_user`). `POST /ingest` (the Flutter app's manual trigger) calls `run_for_user` for the calling account directly, bypassing the due-check.

Any adapter-level failure (bad feed URL, network error, missing credentials) is caught and logged inside that adapter — it contributes zero candidates and does not abort the run. Only an unexpected failure in matching/dedup/persistence/notification aborts that user's run, and even then the run is recorded as `failed` with the error message before the exception propagates (and `run_all_users()` continues on to the next user). Persistence (dedup) and notification delivery are independent: a channel outage delays a job's alert to a later run rather than losing it, since the job isn't marked `notified_at` until delivery actually succeeds on at least one configured channel.

### Per-source visibility

`SafeAdapterRegistry.fetch_all()` logs one INFO line per source (`Source 'X': checked, fetched N candidate(s)`, or `disabled, skipped`) plus a summary line with every source's count. `IngestionService.run()` additionally computes a matched-count-per-source breakdown and logs both breakdowns together, and returns them in its result dict as `fetched_by_source` / `matched_by_source` (in addition to the existing aggregate `fetched`/`matched`/`new`/`delivered`). `scripts/run_ingestion_once.py` renders that breakdown as a per-source table in the GitHub Actions step summary, so you can see exactly which sources returned how much without reading raw logs — see [OPERATIONS.md](OPERATIONS.md#run-history--logs).

## API reference

Every endpoint below except `/health`, `POST /auth/signup`, and `POST /auth/login` requires header `Authorization: Bearer <token>` (a session token from signup/login — see `bot_docs/OPERATIONS.md`'s "Accounts and multi-user"). Every response is scoped to the calling account; there's no way to read or modify another user's data through the API.

- `GET /health` → `{"status": "ok"}`
- `POST /auth/signup` — `{"email", "password", "invite_code"}` (`invite_code` required only if `SIGNUP_INVITE_CODE` is set) → `{"user": {...}, "token": "..."}`. 409 on an email already in use, 403 on a missing/wrong invite code.
- `POST /auth/login` — `{"email", "password"}` → `{"user": {...}, "token": "..."}`. 401 on wrong credentials.
- `POST /auth/logout` — deletes the current session server-side.
- `GET /jobs` / `POST /jobs` (409 on duplicate `link` for this account)
- `GET /preferences` / `POST /preferences` (body includes `kind: "include"|"exclude"`, 409 on duplicate) / `DELETE /preferences/{id}`
- `GET /ingestion/settings` / `PUT /ingestion/settings` — reading/updating this account's source toggles and poll interval.
- `GET /notification-settings` / `PUT /notification-settings` — reading/updating this account's Telegram/Slack/Discord channel config.
- `POST /ingest` — runs this account's ingestion pass immediately, bypassing the scheduler's due-check. Returns `{"fetched", "matched", "new", "delivered", "fetched_by_source", "matched_by_source"}`.
- `GET /ingestion/runs?limit=20` — this account's history of past ingestion runs (newest first): timestamps, status (`success`/`failed`), counts, and the error message for failed runs.
- `POST /ingest/keywords` — bulk-replaces this account's `include`/`exclude` preference lists:
  ```json
  { "include_keywords": ["backend", "flutter", "python"], "exclude_keywords": ["senior", "manager"] }
  ```

## Notes

- The backend listens on `http://127.0.0.1:9000`; the frontend targets the same.
- `POST /ingest` (also triggered by the Flutter "Check for new jobs now" button) is a manual on-demand run of the exact same per-user pipeline the scheduler runs automatically — safe to call anytime, including while a scheduled run might be in flight, since dedup is atomic at the database layer.
- `CORS` is wide open (`allow_origins=["*"]`) for local development; tighten before exposing this beyond `127.0.0.1`.
