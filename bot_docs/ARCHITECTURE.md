# Architecture

## Overview

The application has three main layers, and is multi-user: every account (email+password, see "Accounts" below) gets its own independently-scoped keyword preferences, ingestion source toggles, notification channels, and job history, all backed by a shared Postgres database (`DATABASE_URL`). The legacy `backend/job_alert.db` SQLite file (once committed to git and kept in sync by the hourly ingestion workflow) is no longer the source of truth — see `backend/scripts/migrate_sqlite_to_postgres.py` for the one-time cutover and `bot_docs/OPERATIONS.md` for the reasoning.

- **Backend API**: FastAPI service exposing auth (signup/login/logout), job, preference, ingestion-settings, notification-settings, and ingestion endpoints — every one of them (except `/health` and the two auth-entry routes) scoped to whichever account the request's session token belongs to.
- **Ingestion pipeline**: a systemd timer on VM2 (`job-alert-worker.timer`) ticks every 15 minutes and runs the same pipeline the API exposes manually, once per account that's actually due for a check — fetch candidate jobs from that account's enabled sources, match them against that account's saved keywords, deduplicate against that account's previously-seen jobs, persist new ones, and send a digest to that account's configured channels (Telegram/Slack/Discord). This is deliberately the *only* place ingestion is scheduled — see "Deploying to OCI" in `bot_docs/OPERATIONS.md` for why a prior in-process scheduler and a GitHub Actions cron were both retired in favor of this single mechanism.
- **Frontend UI**: a Flutter dashboard, gated behind a login screen, that displays the logged-in account's stored jobs, lets you trigger an on-demand check, and configures sources/keywords/notifications for that account. It's a secondary control panel — the backend keeps running and alerting on its own schedule whether or not the app is open.

### Accounts

`users`/`sessions` tables back email+password login (bcrypt-hashed passwords, opaque bearer session tokens — see `backend/app/core/security.py`). Signup can optionally require an invite code (`SIGNUP_INVITE_CODE`). See `bot_docs/OPERATIONS.md`'s "Accounts and multi-user" section for the operational side of this (setup, upgrading a pre-accounts install, what stays global vs. per-account).

## Backend

- `backend/main.py`
  - FastAPI application bootstrap with a `lifespan` hook: opens the Postgres connection pool on startup (failing fast if `DATABASE_URL` is wrong/unreachable, rather than on the first request), closes it on shutdown. Schema itself is applied separately via `alembic upgrade head` (see "Database and migrations" below) — this hook no longer creates tables. Does not start any scheduler — this process is the API only; ingestion scheduling lives entirely on VM2 (see `bot_docs/OPERATIONS.md`'s "Deploying to OCI").
  - Registers CORS middleware and the API router.
- `backend/app/api/routes.py`
  - HTTP endpoints for auth, jobs, preferences, ingestion settings, notification settings, ingestion, and ingestion run history. Services are wired in via FastAPI `Depends`; every protected handler also depends on `get_current_user` and passes `current_user.id` down. `resume_routes.py`'s router (see "Resume upload and parsing" below) is included into the `protected` sub-router (`protected.include_router(resume_routes.router)`) rather than added directly here, so `routes.py` doesn't grow without bound as more feature areas (this one, then matching) get added — each new area gets its own router module.
- `backend/app/services/`
  - `auth_service.py`: signup/login/logout.
  - `job_service.py` / `preference_service.py` / `ingestion_settings_service.py` / `ingestion_run_service.py` / `notification_settings_service.py` / `resume_service.py`: business logic, one service per entity, each method taking a `user_id`.
  - `errors.py`: `DuplicateResourceError` (uniqueness conflict → `HTTPException(409)`), `InvalidCredentialsError` (bad login/invite code → 401/403), `ResumeUploadLimitExceeded` (daily cap hit → 429), `AIExtractionError` (Gemini failed, or a PDF yielded no text → 502). All raised by repositories/services and translated in routes.
- `backend/app/repositories/`
  - `user_repository.py` / `session_repository.py`: accounts and login sessions.
  - `job_repository.py` / `preference_repository.py` / `ingestion_settings_repository.py` / `ingestion_run_repository.py` / `notification_settings_repository.py` / `resume_repository.py`: Postgres persistence via psycopg (hand-written parameterized SQL, no ORM), one repository per entity, every query scoped by `user_id`.
- `backend/app/db/database.py`
  - `get_pool()`: a module-level `psycopg_pool.ConnectionPool` (lazily created, conservatively sized — see "Footprint" below), with `pgvector.psycopg.register_vector` wired in via the pool's `configure` hook so `vector` columns round-trip as plain Python lists/arrays.
  - `db_session()`: a context manager that checks out a pooled connection, commits on success, rolls back on error. Schema is no longer created here at all — see "Database and migrations."

### Database and migrations

Schema changes are versioned Alembic migrations (`backend/alembic/versions/`), applied explicitly via `alembic upgrade head` as a deploy step (see `deploy/oci_deploy_db.sh`) — not implicitly on every app boot, the way SQLite's `_migrate_add_x()` functions used to run inside `init_db()`. That pattern existed only because SQLite has no real `ALTER TABLE`/transactional DDL story; Postgres does, so there's no more reason to re-check "does this column exist yet" on every startup. Alembic depends on SQLAlchemy for its own migration-runner engine only (`backend/alembic/env.py`) — the project does not use the SQLAlchemy ORM anywhere; repositories still write plain parameterized SQL through psycopg, migrations are hand-written `op.execute()` SQL rather than autogenerated from ORM models.

`0001_initial_schema.py` is the full schema, including the AI-personalization tables (`resume_profiles`, `resume_upload_events`) and `jobs.embedding`/`embedding_model`/`embedded_at` — see the matching-engine design further down.

### Footprint

If Postgres and the ingestion/matching worker run on the same small VM (see the OCI deploy docs), tune `shared_buffers`/`max_connections` down from Postgres's defaults and keep the connection pool small (`get_pool()`'s `min_size=1, max_size=5`) — this setup is sized for light personal/demo use, not concurrent high-throughput traffic.

- `backend/app/ingestion/`
  - `services/ingestion_service.py`: `run_for_user(user_id)` orchestrates one account's ingestion run — build the adapter registry from that account's settings, build the matcher from their keyword preferences, fetch, match, dedup, persist, notify via their `NotificationSettings`, and record the outcome to `ingestion_runs`. `run_all_users()` loops every account, skipping anyone not yet due.
  - `services/matcher_service.py`: include/exclude keyword matching against title/company/location.
  - `services/dedup_service.py`: in-batch dedup (catches two adapters returning the same link in one run). Cross-run dedup is handled atomically at the DB layer via `jobs.link UNIQUE` + `INSERT ... ON CONFLICT DO NOTHING`.
  - `services/notification_service.py`: sends a digest to every channel (Telegram/Slack/Discord) a given user has configured (`NotificationSettings`, per-user, see `notification_settings_repository.py`), for jobs pending delivery (`JobRepository.list_unnotified(user_id)` -- this run's new matches plus any left over from a run whose send failed partway through, bounded at 200 oldest-first per run so a multi-day outage doesn't try to flush an ever-growing backlog in one go), and returns the ids delivered to at least one channel. `IngestionService.run_for_user()` marks only those ids `notified_at` via `JobRepository.mark_notified()`, so an outage delays delivery rather than losing it -- persistence (which drives dedup) and delivery are decoupled.
  - `adapters/rss_adapter.py`: fetches and parses a configured RSS/Atom feed (most Tier A sources).
  - `adapters/remoteok_adapter.py`: fetches RemoteOK's JSON API (its RSS feed was discontinued) — a dedicated adapter since the payload isn't RSS/Atom.
  - `adapters/ats_adapters.py`: `GreenhouseAdapter`/`LeverAdapter`/`AshbyAdapter` — pull postings directly from a company's public ATS job-board API (Tier C, gated by `allow_direct_scraping`, not `enable_rss_sources`). One instance per configured board token, registered dynamically from the comma-separated `GREENHOUSE_BOARD_TOKENS`/`LEVER_COMPANY_SLUGS`/`ASHBY_BOARD_NAMES` env vars — see [SOURCES.md](SOURCES.md).
  - `adapters/foundit_adapter.py`: `FounditAdapter` — pulls from Foundit's own internal (undocumented) search API, one instance per configured query term. Also gated by `allow_direct_scraping`. Uses a different User-Agent than the other adapters, since Foundit's edge keyword-blocks the literal substring "bot" — see [SOURCES.md](SOURCES.md) for the full rationale before touching this one.
  - `adapters/unstop_adapter.py`: `UnstopAdapter` — pulls from Unstop's own internal (undocumented) listing API. Also gated by `allow_direct_scraping`. No per-query configuration; fetches the latest open postings in bulk and relies on normal keyword matching, same as the RSS sources — see [SOURCES.md](SOURCES.md).
  - `adapters/email_adapter.py` + `adapters/email_parsers.py`: reads LinkedIn/Naukri/Indeed job-alert emails via IMAP and parses postings out of the HTML body (Tier B — never talks to linkedin.com/naukri.com/indeed.com directly). `EmailAdapter` searches every mailbox in a configured list (INBOX plus, optionally, a Gmail label folder), bounded to the last `LOOKBACK_DAYS` (3) days via IMAP's `SINCE` — see [SOURCES.md](SOURCES.md). LinkedIn's and Indeed's parsers are validated against real alert emails; Naukri's is still best-effort (no real job-digest sample has been available to check it against). Deliberately does not rely on IMAP's `\Seen`/`UNSEEN` flag to decide what's new -- see `ProcessedAlertEmailRepository` below.
  - `repositories/processed_alert_email_repository.py`: tracks which alert-email Message-IDs `EmailAdapter` has already turned into candidates, independent of the mailbox's own read state (a Gmail filter with "mark as read" as one of its actions, or the user simply reading their own mail, previously made an IMAP `UNSEEN` search silently skip real alerts forever — see [SOURCES.md](SOURCES.md)).

### Resume upload and parsing

- `backend/app/ai/` — provider-specific AI code, isolated the same way `app/ingestion/adapters/` isolates each job source (swappable/testable without touching callers):
  - `pdf_extractor.py`: `extract_text(pdf_bytes) -> str`, via `pypdf` (pure-Python, no system deps — appropriate for the 1GB deploy VMs). Resumes are simple text documents where pypdf's per-page extraction is adequate; if some resume template extracts poorly, swapping to `pdfplumber` only touches this one function.
  - `gemini_client.py`: `GeminiClient.extract_resume_profile(text) -> dict` and `.embed_text(text) -> list[float]`, wrapping the `google-genai` SDK. Extraction uses Gemini's structured-output mode (`response_schema=ResumeExtraction`, a Pydantic model) rather than prompting for free text and parsing it after the fact — a schema-conforming response is required, or the client raises. Embeddings always request `output_dimensionality=768` explicitly (`EMBEDDING_DIMENSIONS`), matching the `vector(768)` columns, regardless of which embedding model `GEMINI_EMBEDDING_MODEL` points at.
- `backend/app/services/resume_service.py` — `ResumeService.upload(user_id, pdf_bytes, filename)` orchestrates, in order: check the per-user daily upload cap (`ResumeRepository.count_uploads_since`, cheap — done *before* any Gemini call) → extract PDF text → Gemini structured extraction → Gemini embedding → upsert via `ResumeRepository` → record the upload event. Any Gemini failure (including `GOOGLE_API_KEY` being unset, which fails lazily on first use, not at service construction) is caught and re-raised as `AIExtractionError`, so it surfaces as a clean `502`, not an unhandled `500`. `get_profile`/`delete` are thin passthroughs to the repository.
- `backend/app/repositories/resume_repository.py` — `upsert` is a single `INSERT ... ON CONFLICT (user_id) DO UPDATE`: one row per user, reupload replaces it. `uploaded_at` is set once (first upload, via `DEFAULT now()`) and left out of the `ON CONFLICT` `SET` clause so it never moves; `updated_at` is set on every upsert. `count_uploads_since`/`record_upload_event` back the daily cap via the append-only `resume_upload_events` table (see "Postgres tables" below) rather than a shared counter column, avoiding a race under concurrent requests.
- **The original PDF is never stored** — only the extracted plain text (`resume_profiles.resume_text`), the structured JSON profile, and the embedding vector. Discarded immediately after parsing.
- `backend/app/api/resume_routes.py` — `POST /resume` (multipart upload, replaces any existing profile, `413` over 5MB, `400` on a non-PDF content type, `429`/`502` from the errors above), `GET /resume` (current profile or `null`), `DELETE /resume`.

### Job matching

Personalized matching is a re-ranking layer on top of the existing per-user keyword ingestion, not a replacement or a separate data source — `GET /matches` only ever ranks jobs that a user's *own* keyword/source configuration already pulled in (the `jobs.UNIQUE(user_id, link)` pool). A narrow keyword filter means a narrow match pool; this is a deliberate v1 scope decision. A shared/global job pool (one user's ingestion enriching everyone's matches) is explicitly out of scope — it would need splitting `jobs` into a shared postings table plus per-user visibility, real schema surgery, not a v1-sized change.

- `backend/app/ingestion/services/embedding_service.py` — `EmbeddingService.embed_job(job)` embeds `f"{title}\n{company}\n{location}"` (the only fields `JobCandidate` carries — no description field exists) and writes it via `JobRepository.set_embedding()`. Called from `IngestionService.run_for_user()` right after a candidate is confirmed genuinely new (once per job, at creation time — never re-embedded per match query, which is what keeps `GET /matches` a pure SQL query with no Gemini calls in the request path). A per-job embed failure is caught and logged, not raised — the job still gets inserted and still serves keyword-based alerts, it just won't appear in personalized matches until the next backfill sweep picks it up.
- `backend/scripts/backfill_job_embeddings.py` — one-off sweep for jobs that predate embedding-at-ingestion-time (migrated from the legacy SQLite DB) or whose embed call failed and was never retried. Keyset-paginated on job id (`JobRepository.list_jobs_missing_embedding(after_id=...)`), not a naive "first N still missing" query — a job whose embed call keeps failing would otherwise reappear at the front of every batch forever instead of the sweep making forward progress through the table. Safe to re-run.
- `backend/app/services/matching_service.py` — `MatchingService.get_matches(user_id, limit, offset)` loads the caller's resume embedding (`ResumeRepository.get_embedding`, an internal method distinct from `get()` — the public `ResumeProfile` model doesn't expose the raw vector) and returns `[]` if none exists yet (a clear "upload a resume to see matches" empty state, not an error).
- `backend/app/repositories/matching_repository.py` — the actual ranking query: `ORDER BY embedding <=> :resume_embedding` (pgvector cosine distance), `1 - distance` as `match_score`, `WHERE user_id = :user_id AND embedding IS NOT NULL`. The query parameter must be wrapped in `pgvector.utils.Vector(...)`, not passed as a plain Python list — confirmed empirically against a live pgvector instance: a bare list adapts to a Postgres array by default and fails with `operator does not exist: vector <=> double precision[]`, since `register_vector()` (`app/db/database.py`) only registers dumpers for `numpy.ndarray` and `Vector`, not `list`. (Passing a plain list into an `INSERT` on a `vector`-typed column works fine, via Postgres's implicit array→vector cast when the target column type is known — it's specifically the `<=>` operator context, where Postgres has to resolve an operator overload rather than cast into a known column type, that needs the explicit wrapper.)
- `backend/app/api/matching_routes.py` — `GET /matches?limit=20&offset=0`, plain `LIMIT`/`OFFSET` pagination (fine at this data scale, same style as `GET /ingestion/runs`).

- `backend/app/core/config.py`
  - Static, deployment-wide configuration read from environment variables (IMAP credentials, alert sender addresses, feed URLs, adapter API keys, optional `SIGNUP_INVITE_CODE`, `GOOGLE_API_KEY`/`GEMINI_EXTRACTION_MODEL`/`GEMINI_EMBEDDING_MODEL`/`RESUME_UPLOAD_DAILY_CAP`, `SIGNUP_RATE_LIMIT`/`LOGIN_RATE_LIMIT`). Per-user data (notification channels, keyword preferences, ingestion toggles, resume profile) lives in the DB instead, not here.
- `backend/app/core/rate_limit.py`
  - A single shared `slowapi.Limiter` instance (in-memory storage, per-IP via `get_remote_address` — fine at this project's single-process scale, no Redis needed), wired into `main.py` (app state, exception handler, `SlowAPIMiddleware`) and applied to `POST /auth/signup`/`POST /auth/login` via `@limiter.limit(...)` in `routes.py`. Since decorators apply once at import time, the rate limit string is read from `settings` when the module loads, not per-request — tests that need a different limit can't monkeypatch it after the fact, only exercise the real configured value (see `tests/test_rate_limit.py`). Open signup (no invite code required by default) is what makes this necessary — it's what actually stands between a public deployment and someone scripting account creation or password-guessing.
- `backend/app/core/security.py`
  - `hash_password`/`verify_password`: bcrypt-backed password hashing.
  - `get_current_user`: resolves `Authorization: Bearer <token>` to a `User` via `SessionRepository` + `UserRepository`, 401s on missing/invalid/expired. Applied to every route except `/health`, `/auth/signup`, and `/auth/login` (see `routes.py`'s `protected` sub-router). Replaced the older `require_api_key` shared-secret gate once real per-user accounts existed — see `bot_docs/OPERATIONS.md`'s "Accounts and multi-user" section.
- `backend/app/services/auth_service.py`
  - `AuthService.signup`/`login`/`logout` — signup optionally checks `SIGNUP_INVITE_CODE` (constant-time compare), both signup and login create a session token (`SessionRepository.create`, 30-day default expiry), logout deletes it.
- `backend/scripts/run_ingestion_once.py`
  - Short-lived entrypoint for a single multi-user ingestion pass (`IngestionService.run_all_users()`) — what VM2's `job-alert-worker.timer` actually runs every 15 minutes in production (see `bot_docs/OPERATIONS.md`'s "Deploying to OCI"). Also usable manually for local ingestion runs (`python -m scripts.run_ingestion_once`) without running the API at all.

## Frontend

- `frontend/lib/main.dart` — app entry point; awaits `ApiService.instance.init()` (loads the persisted backend URL) and `AuthService.instance.init()` (loads any persisted session) before the first frame, sets up the "premium minimal dark SaaS" Material 3 theme (`theme/app_theme.dart`, light/dark), and roots the widget tree at `AuthGate` (below) instead of `HomeScreen` directly.
- `frontend/lib/main.dart`'s `AuthGate` — swaps between `LoginScreen` and `HomeScreen` based on `AuthService.instance.isLoggedIn`, listening to `AuthService` (a `ChangeNotifier`) so login/signup/logout/session-expiry all take effect immediately with no routing package involved.
- `frontend/lib/screens/login_screen.dart` / `signup_screen.dart` — email+password auth forms; signup has an optional invite-code field (only enforced if the backend has `SIGNUP_INVITE_CODE` set).
- `frontend/lib/screens/home_screen.dart` — a two-tab shell (`NavigationBar`: Jobs / For You) over an `IndexedStack`, so switching tabs doesn't refetch. `_JobsTab` (private, in the same file) is the original dashboard content unchanged -- stored jobs as source-colored cards with a company-logo avatar falling back to an initial, tap to copy the link, and an on-demand "Check for new jobs now" trigger. The unreachable-backend error state and the single settings AppBar icon both link to `SettingsHubScreen`; a `GlobalKey<_JobsTabState>` lets the AppBar's settings button reload the Jobs tab specifically after returning (settings can change what it shows; matches aren't affected by ingestion source/keyword toggles the same way, so only Jobs needs this).
- `frontend/lib/screens/matches_tab.dart` — the "For You" tab: `GET /matches` rendered as cards with a match-score percentage badge, same card/avatar/copy-link pattern as `_JobsTab`. Empty state (no resume uploaded yet) routes straight to `ResumeUploadScreen`.
- `frontend/lib/screens/settings_hub_screen.dart` — single settings home (replacing several separate AppBar icons): navigation to resume, ingestion sources, keywords, notifications, server connection, run history, plus log out.
- `frontend/lib/screens/resume_upload_screen.dart` — PDF file picker (`file_picker`, cross-platform including web) + upload, shows the parsed profile (skills/titles/education/locations as chips, seniority/years-experience summary) once processed, delete option. `GET`/`POST`/`DELETE /resume`.
- `frontend/lib/screens/config_screen.dart` — loads/saves this account's ingestion source toggles and poll interval against the backend.
- `frontend/lib/screens/keyword_config_screen.dart` — loads this account's saved keywords and updates include/exclude filters.
- `frontend/lib/screens/notification_settings_screen.dart` — loads/saves this account's Telegram/Slack/Discord channel config (`GET`/`PUT /notification-settings`).
- `frontend/lib/screens/server_settings_screen.dart` — lets the user view/edit/test the backend base URL (needed on a real device, where `127.0.0.1` means the phone itself, not the PC running the backend — see [OPERATIONS.md](OPERATIONS.md#running-on-a-phone-androidios)). No longer has an API-key field — auth is per-account login now, not a shared secret.
- `frontend/lib/screens/run_history_screen.dart` — recent ingestion runs (status, timestamps, fetched/matched/new/delivered counts, error message on failure), backed by `GET /ingestion/runs`.
- `frontend/lib/services/api_service.dart` — the only place that talks HTTP to the backend; a singleton (`ApiService.instance`) so every screen shares one live base URL, with per-request timeouts. Every request carries `Authorization: Bearer <token>` when logged in; a 401 on an already-authenticated call triggers `AuthService.logout()` so an expired session drops back to the login screen instead of showing a generic error. `uploadResume()` is the one exception to the JSON-body `_get`/`_post` helpers -- it builds a `MultipartRequest` directly, since it's uploading a file. `fetchMatches()` goes through the normal `_get` helper.
- `frontend/lib/services/auth_service.dart` — holds the current session token/email, persisted via `shared_preferences`; `signup`/`login`/`logout` wrap the matching `ApiService` calls and `notifyListeners()` so `AuthGate` reacts immediately.
- `frontend/lib/services/server_config.dart` — resolves the platform-appropriate default backend URL and persists the user's URL override via `shared_preferences`.
- `frontend/lib/theme/app_colors.dart` / `app_theme.dart` — the design-token system (dark-first color scheme, semantic success/warning colors via a `ThemeExtension`, per-source brand colors/labels) referenced by every screen instead of hardcoded literals.
- `frontend/lib/widgets/section_label.dart` — shared small section-header widget.
- `frontend/android/`, `frontend/ios/` — native platform scaffolding (added for mobile support). Android allows cleartext (plain HTTP) traffic and declares the `INTERNET` permission; iOS scopes `NSAllowsLocalNetworking` in `Info.plist` — both needed since the backend has no TLS and is only reachable on the local network.

## Data model and schema

### Postgres tables

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
- `resume_profiles`
  - One row per user (`user_id` PRIMARY KEY, upsert-on-reupload): `resume_text` (extracted plain text), `profile_json` (structured skills/titles/years_experience/seniority/locations/education, extracted via Gemini), `embedding` (`vector(768)`, via Gemini's embedding endpoint), `embedding_model`, `source_filename`, `uploaded_at`, `updated_at`. The original uploaded PDF is never stored — only what's extracted from it.
- `resume_upload_events`
  - Append-only: `id`, `user_id`, `uploaded_at`. Backs the per-user daily resume-upload cap (protects the free Gemini quota) via `COUNT(*) WHERE uploaded_at > now() - interval '1 day'`, rather than a shared counter column that could race under concurrent requests.

There is no separate "seen jobs" table — `jobs`'s `UNIQUE(user_id, link)`, combined with an atomic `INSERT ... ON CONFLICT DO NOTHING`, is the single dedup mechanism. `jobs` also carries `embedding`/`embedding_model`/`embedded_at` (nullable — a job is fully usable for keyword-based alerting before it's ever embedded), populated once per job at ingestion time and used for resume-based matching (`GET /matches`) via pgvector cosine distance (`<=>`). No ANN index (IVFFlat/HNSW) is used yet — brute-force scan is fast enough at this project's scale; add one once `jobs` exceeds roughly 50k rows.

## Ingestion flow

`IngestionService.run_for_user(user_id)` is one pass for a single account:

1. Load that user's `ingestion_settings` and build the adapter registry — each adapter is enabled/disabled per its own toggle + (deployment-wide) feed URL/credentials.
2. Load that user's `preferences` (include/exclude keyword filters, each optionally scoped to a `location`) and build the matcher.
3. Fetch candidates from every enabled adapter (RSS/JSON sources + email-alert sources).
4. Match each candidate against the include/exclude keyword filters (whole-word match against title/company/location; a filter with a `location` set only applies when the candidate's location also matches it).
5. In-batch dedup (two adapters returning the same link in one run).
6. Persist: `INSERT ... ON CONFLICT DO NOTHING` per candidate — `jobs.UNIQUE(user_id, link)` silently drops anything already seen for this user in a prior run. Newly-persisted jobs start with `notified_at = NULL`.
7. Embed each genuinely-new job (`EmbeddingService.embed_job`, see "Job matching" above) — once per job, right here at ingestion time, never re-embedded per match query. A failure here is caught and logged, not raised; it doesn't affect steps 8-9.
8. Send a digest (to every channel in that user's `notification_settings`) for every job still pending delivery (`notified_at IS NULL`) — this run's new matches plus any left over from a run whose send failed partway through — and mark only the ones actually delivered.
9. Record the run outcome (counts, status, error if any) to `ingestion_runs`, scoped to that user.

`IngestionService.run_all_users()` — what the scheduler tick and `scripts/run_ingestion_once.py` actually call — loops every user, checks each one's `poll_interval_hours` against their own `most_recent_finished_at`, and calls `run_for_user` only for whoever is actually due. One user's failure doesn't stop the rest (already caught/logged/recorded inside `run_for_user`). `POST /ingest` (the Flutter app's manual trigger) calls `run_for_user` for the calling account directly, bypassing the due-check.

Any adapter-level failure (bad feed URL, network error, missing credentials) is caught and logged inside that adapter — it contributes zero candidates and does not abort the run. Only an unexpected failure in matching/dedup/persistence/notification aborts that user's run, and even then the run is recorded as `failed` with the error message before the exception propagates (and `run_all_users()` continues on to the next user). Persistence (dedup) and notification delivery are independent: a channel outage delays a job's alert to a later run rather than losing it, since the job isn't marked `notified_at` until delivery actually succeeds on at least one configured channel.

### Per-source visibility

`SafeAdapterRegistry.fetch_all()` logs one INFO line per source (`Source 'X': checked, fetched N candidate(s)`, or `disabled, skipped`) plus a summary line with every source's count. `IngestionService.run()` additionally computes a matched-count-per-source breakdown and logs both breakdowns together, and returns them in its result dict as `fetched_by_source` / `matched_by_source` (in addition to the existing aggregate `fetched`/`matched`/`new`/`delivered`). In production this is visible via `sudo journalctl -u job-alert-worker.service` on VM2 — see [OPERATIONS.md](OPERATIONS.md#run-history--logs).

## API reference

Every endpoint below except `/health`, `POST /auth/signup`, and `POST /auth/login` requires header `Authorization: Bearer <token>` (a session token from signup/login — see `bot_docs/OPERATIONS.md`'s "Accounts and multi-user"). Every response is scoped to the calling account; there's no way to read or modify another user's data through the API.

- `GET /health` → `{"status": "ok"}`
- `POST /auth/signup` — `{"email", "password", "invite_code"}` (`invite_code` required only if `SIGNUP_INVITE_CODE` is set) → `{"user": {...}, "token": "..."}`. 409 on an email already in use, 403 on a missing/wrong invite code, 429 over `SIGNUP_RATE_LIMIT` (5/hour by default, per IP).
- `POST /auth/login` — `{"email", "password"}` → `{"user": {...}, "token": "..."}`. 401 on wrong credentials, 429 over `LOGIN_RATE_LIMIT` (10/15min by default, per IP).
- `POST /auth/logout` — deletes the current session server-side.
- `GET /jobs` / `POST /jobs` (409 on duplicate `link` for this account)
- `GET /preferences` / `POST /preferences` (body includes `kind: "include"|"exclude"`, 409 on duplicate) / `DELETE /preferences/{id}`
- `GET /ingestion/settings` / `PUT /ingestion/settings` — reading/updating this account's source toggles and poll interval.
- `GET /notification-settings` / `PUT /notification-settings` — reading/updating this account's Telegram/Slack/Discord channel config.
- `POST /ingest` — runs this account's ingestion pass immediately, bypassing the scheduler's due-check. Returns `{"fetched", "matched", "new", "delivered", "fetched_by_source", "matched_by_source"}`.
- `POST /resume` — multipart PDF upload (field name `file`), replaces this account's existing resume profile if any. Returns the parsed `ResumeProfile`. `400` on a non-PDF content type, `413` over 5MB, `429` if the daily upload cap (`RESUME_UPLOAD_DAILY_CAP`) is hit, `502` if Gemini fails or the PDF has no extractable text.
- `GET /resume` — this account's current resume profile, or `null` if none uploaded yet.
- `DELETE /resume` — deletes this account's resume profile.
- `GET /matches?limit=20&offset=0` — this account's jobs ranked by resume similarity (`match_score`, highest first). Empty list if no resume has been uploaded yet, or if none of this account's ingested jobs have been embedded yet.
- `GET /ingestion/runs?limit=20` — this account's history of past ingestion runs (newest first): timestamps, status (`success`/`failed`), counts, and the error message for failed runs.
- `POST /ingest/keywords` — bulk-replaces this account's `include`/`exclude` preference lists:
  ```json
  { "include_keywords": ["backend", "flutter", "python"], "exclude_keywords": ["senior", "manager"] }
  ```

## Notes

- The backend listens on `http://127.0.0.1:9000` locally; in production, nginx on VM1 terminates TLS and proxies `/api/` to it (see `bot_docs/OPERATIONS.md`'s "Deploying to OCI").
- `POST /ingest` (also triggered by the Flutter "Check for new jobs now" button) is a manual on-demand run of the exact same per-user pipeline the worker timer runs automatically — safe to call anytime, including while a scheduled run might be in flight, since dedup is atomic at the database layer.
- `CORS` (`app/middleware.py`) is driven by `ALLOWED_ORIGIN` (`app/core/config.py`) — wide open (`"*"`) by default for local development, set to the real deployed origin (e.g. `https://job-alert-app.duckdns.org`) in production. Note this only matters for cross-origin browser requests (native Flutter builds and the web build served same-origin through nginx aren't affected by CORS at all) — it's not the thing protecting the API itself, `get_current_user`'s session-token check is.
