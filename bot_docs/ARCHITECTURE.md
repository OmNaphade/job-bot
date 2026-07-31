# Architecture

## Overview

The application has three main layers:

- **Backend API**: FastAPI service exposing job, preference, ingestion-settings, and ingestion endpoints.
- **Ingestion pipeline**: a background scheduler runs the same pipeline the API exposes manually — fetch candidate jobs from enabled sources, match them against saved keywords, deduplicate against previously-seen jobs, persist new ones, and send a Telegram digest.
- **Frontend UI**: a Flutter dashboard that displays stored jobs, lets you trigger an on-demand check, and configures sources/keywords. It's a secondary control panel — the backend keeps running and alerting on its own schedule whether or not the app is open.

## Backend

- `backend/main.py`
  - FastAPI application bootstrap with a `lifespan` hook: initializes the database and starts the background scheduler on startup, stops the scheduler on shutdown.
  - Registers CORS middleware and the API router.
- `backend/app/api/routes.py`
  - HTTP endpoints for health checks, jobs, preferences, ingestion settings, ingestion, and ingestion run history. Services are wired in via FastAPI `Depends`.
- `backend/app/services/`
  - `job_service.py` / `preference_service.py` / `ingestion_settings_service.py` / `ingestion_run_service.py`: business logic, one service per entity.
  - `errors.py`: `DuplicateResourceError`, raised by repositories on a uniqueness conflict and translated to `HTTPException(409)` in routes.
- `backend/app/repositories/`
  - `job_repository.py` / `preference_repository.py` / `ingestion_settings_repository.py` / `ingestion_run_repository.py`: SQLite persistence, one repository per entity.
- `backend/app/db/database.py`
  - `init_db()`: creates all tables once at startup (not per-request).
  - `db_session()`: a context manager that commits on success, rolls back on error, and always closes the connection.
- `backend/app/ingestion/`
  - `scheduler.py`: wraps an APScheduler `BackgroundScheduler` that runs the ingestion pipeline on an interval (`poll_interval_hours`, configurable at runtime).
  - `services/ingestion_service.py`: orchestrates one ingestion run — build the adapter registry from current settings, build the matcher from current keyword preferences, fetch, match, dedup, persist, notify, and record the outcome (success or failure) to `ingestion_runs`.
  - `services/matcher_service.py`: include/exclude keyword matching against title/company/location.
  - `services/dedup_service.py`: in-batch dedup (catches two adapters returning the same link in one run). Cross-run dedup is handled atomically at the DB layer via `jobs.link UNIQUE` + `INSERT OR IGNORE`.
  - `services/notification_service.py`: sends a Telegram digest message for newly-persisted matches.
  - `adapters/rss_adapter.py`: fetches and parses a configured RSS/Atom feed (most Tier A sources).
  - `adapters/remoteok_adapter.py`: fetches RemoteOK's JSON API (its RSS feed was discontinued) — a dedicated adapter since the payload isn't RSS/Atom.
  - `adapters/ats_adapters.py`: `GreenhouseAdapter`/`LeverAdapter`/`AshbyAdapter` — pull postings directly from a company's public ATS job-board API (Tier C, gated by `allow_direct_scraping`, not `enable_rss_sources`). One instance per configured board token, registered dynamically from the comma-separated `GREENHOUSE_BOARD_TOKENS`/`LEVER_COMPANY_SLUGS`/`ASHBY_BOARD_NAMES` env vars — see [SOURCES.md](SOURCES.md).
  - `adapters/foundit_adapter.py`: `FounditAdapter` — pulls from Foundit's own internal (undocumented) search API, one instance per configured query term. Also gated by `allow_direct_scraping`. Uses a different User-Agent than the other adapters, since Foundit's edge keyword-blocks the literal substring "bot" — see [SOURCES.md](SOURCES.md) for the full rationale before touching this one.
  - `adapters/unstop_adapter.py`: `UnstopAdapter` — pulls from Unstop's own internal (undocumented) listing API. Also gated by `allow_direct_scraping`. No per-query configuration; fetches the latest open postings in bulk and relies on normal keyword matching, same as the RSS sources — see [SOURCES.md](SOURCES.md).
  - `adapters/email_adapter.py` + `adapters/email_parsers.py`: reads LinkedIn/Naukri job-alert emails via IMAP and parses postings out of the HTML body (Tier B — never talks to linkedin.com/naukri.com directly).
- `backend/app/core/config.py`
  - Static/secret configuration read from environment variables (Telegram token/chat id, IMAP credentials, alert sender addresses, feed URLs).
- `backend/scripts/run_ingestion_once.py`
  - Short-lived entrypoint for a single ingestion pass — what the GitHub Actions scheduled workflow actually runs, as opposed to the long-running `main.py` + APScheduler used for local/always-on operation. Also writes a run summary to the GitHub Actions step summary when running in CI.

## Frontend

- `frontend/lib/main.dart` — app entry point and Material 3 theme (light/dark).
- `frontend/lib/screens/home_screen.dart` — dashboard showing stored jobs (source-colored cards, tap to copy the link) and an on-demand "Check for new jobs now" trigger.
- `frontend/lib/screens/config_screen.dart` — loads/saves real ingestion source toggles and poll interval against the backend.
- `frontend/lib/screens/keyword_config_screen.dart` — loads current saved keywords and updates include/exclude filters.
- `frontend/lib/services/api_service.dart` — the only place that talks HTTP to the backend.
- `frontend/lib/widgets/section_label.dart` — shared small section-header widget.

## Data model and schema

### SQLite tables

- `jobs`
  - `id`, `title`, `company`, `location`, `link` (UNIQUE — the sole dedup key), `source`, `posted_at`
- `preferences`
  - `id`, `keyword`, `kind` (`include` or `exclude`), `location` (stored, not yet used in matching); `UNIQUE(keyword, kind)`
- `ingestion_settings`
  - Single row (`id = 1`): `enable_rss_sources`, `enable_linkedin_alerts`, `enable_naukri_alerts`, `allow_direct_scraping`, `poll_interval_hours`
- `ingestion_runs`
  - One row per ingestion pass (manual or scheduled): `id`, `started_at`, `finished_at`, `status` (`success`/`failed`), `fetched_count`, `matched_count`, `new_count`, `delivered_count`, `error_message`. Written by `IngestionService.run()` itself, in both the success and failure path, so a crashed run is recorded too (see `GET /ingestion/runs`).

There is no separate "seen jobs" table — `jobs.link` being `UNIQUE`, combined with an atomic `INSERT OR IGNORE`, is the single dedup mechanism.

## Ingestion flow (one run)

1. Load current `ingestion_settings` and build the adapter registry — each adapter is enabled/disabled per its own toggle + feed URL/credentials.
2. Load current `preferences` (include/exclude keywords) and build the matcher.
3. Fetch candidates from every enabled adapter (RSS/JSON sources + email-alert sources).
4. Match each candidate against the include/exclude keyword lists (title/company/location).
5. In-batch dedup (two adapters returning the same link in one run).
6. Persist: `INSERT OR IGNORE` per candidate — `jobs.link UNIQUE` silently drops anything already seen in a prior run.
7. Send a Telegram digest for whatever was actually newly persisted.
8. Record the run outcome (counts, status, error if any) to `ingestion_runs`.

Any adapter-level failure (bad feed URL, network error, missing credentials) is caught and logged inside that adapter — it contributes zero candidates and does not abort the run. Only an unexpected failure in matching/dedup/persistence/notification aborts the run, and even then the run is recorded as `failed` with the error message before the exception propagates.

### Per-source visibility

`SafeAdapterRegistry.fetch_all()` logs one INFO line per source (`Source 'X': checked, fetched N candidate(s)`, or `disabled, skipped`) plus a summary line with every source's count. `IngestionService.run()` additionally computes a matched-count-per-source breakdown and logs both breakdowns together, and returns them in its result dict as `fetched_by_source` / `matched_by_source` (in addition to the existing aggregate `fetched`/`matched`/`new`/`delivered`). `scripts/run_ingestion_once.py` renders that breakdown as a per-source table in the GitHub Actions step summary, so you can see exactly which sources returned how much without reading raw logs — see [OPERATIONS.md](OPERATIONS.md#run-history--logs).

## API reference

- `GET /health` → `{"status": "ok"}`
- `GET /jobs` / `POST /jobs` (409 on duplicate `link`)
- `GET /preferences` / `POST /preferences` (body includes `kind: "include"|"exclude"`, 409 on duplicate) / `DELETE /preferences/{id}`
- `GET /ingestion/settings` / `PUT /ingestion/settings` — reading/updating source toggles and poll interval; updating the interval reschedules the background job immediately, no restart needed.
- `POST /ingest` — runs the ingestion pipeline immediately (same logic the scheduler runs automatically). Returns `{"fetched", "matched", "new", "delivered", "fetched_by_source", "matched_by_source"}`.
- `GET /ingestion/runs?limit=20` — history of past ingestion runs (newest first): timestamps, status (`success`/`failed`), counts, and the error message for failed runs.
- `POST /ingest/keywords` — bulk-replaces the `include`/`exclude` preference lists:
  ```json
  { "include_keywords": ["backend", "flutter", "python"], "exclude_keywords": ["senior", "manager"] }
  ```

## Notes

- The backend listens on `http://127.0.0.1:9000`; the frontend targets the same.
- `POST /ingest` (also triggered by the Flutter "Check for new jobs now" button) is a manual on-demand run of the exact same pipeline the scheduler runs automatically — safe to call anytime, including while a scheduled run might be in flight, since dedup is atomic at the database layer.
- `CORS` is wide open (`allow_origins=["*"]`) for local development; tighten before exposing this beyond `127.0.0.1`.
- `preferences.location` is stored but not yet used in matching.
