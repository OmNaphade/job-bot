# Job Alert Platform

A continuously-running, multi-user job-monitoring and personalization platform with a FastAPI backend and a Flutter dashboard. It polls job sources on a schedule, matches new postings against your saved keyword preferences, pushes a Telegram alert the moment something new matches, and — upload a resume — extracts your skills/titles/experience via Gemini to personalize what you see, without you needing to open the app.

[![CI](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml)

## Table of Contents

- [Job Alert Platform](#job-alert-platform)
  - [Table of Contents](#table-of-contents)
  - [About](#about)
  - [Built With](#built-with)
  - [Features](#features)
  - [Demo](#demo)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Configuration](#configuration)
  - [Usage](#usage)
    - [Backend](#backend)
    - [Frontend (dashboard + accounts)](#frontend-dashboard--accounts)
  - [Project Structure](#project-structure)
  - [Documentation](#documentation)
  - [Testing](#testing)
  - [Deployment](#deployment)
  - [Roadmap](#roadmap)
  - [Security](#security)
  - [License](#license)
  - [Contact](#contact)

## About

Job hunting means checking the same handful of boards over and over. This runs the checking for you: an ingestion pipeline fetches candidate postings from several remote-job RSS/JSON feeds, a handful of documented aggregator job-search APIs, your own LinkedIn/Naukri/Indeed saved-search email alerts, and (optionally) specific companies' own Greenhouse/Lever/Ashby job boards, filters them against include/exclude keywords you set, drops anything already seen, and sends a digest to whichever notification channels (Telegram/Slack/Discord) you've configured for what's actually new. It's designed to never scrape LinkedIn/Naukri/Indeed directly — those three go through your own email alerts instead, everything else uses feeds/APIs meant for exactly this kind of consumption.

It runs unattended on a small always-on deployment (two OCI VMs — see [Deployment](#deployment)), so it doesn't depend on a laptop staying on. The Flutter app is an optional dashboard on top, not a requirement for the bot to function.

## Built With

- Python 3.12 / FastAPI (backend API)
- Postgres + pgvector (durable state store; migrations via Alembic)
- A systemd timer on the deployment's worker VM (background polling, every 15 minutes)
- Google Gemini (free tier) — structured resume extraction + embeddings, via `google-genai`
- Flutter / Material 3 (dashboard UI)
- `feedparser` + `requests` (RSS/JSON source adapters); `pypdf` (resume text extraction)
- GitHub Actions (CI only — tests on every push/PR)

## Features

- Multi-user accounts — email/password signup and login (optionally gated by an invite code), each account with its own keyword preferences, source toggles, notification channels, and job history
- Polls 6 verified RSS/JSON remote-job feeds (WeWorkRemotely, Himalayas, Remotive, NoDesk, Jobspresso, RemoteOK) plus Arbeitnow's public job-board API — all no-scraping Tier A sources, no key required
- Optional keyed aggregator job-search APIs — Adzuna, Jooble, and The Muse — for broader, keyword-driven search beyond the fixed remote-job feeds
- LinkedIn/Naukri/Indeed support via your own saved-search email alerts (IMAP), never talks to linkedin.com/naukri.com/indeed.com directly
- Optional direct-from-company-site sources — pulls postings straight from a company's own Greenhouse/Lever/Ashby job board API, per company you configure
- Optional Foundit and Unstop integrations via their own internal (undocumented) APIs — opt-in and more fragile than the other sources, see `bot_docs/SOURCES.md` before enabling
- Include/exclude keyword matching against title/company/location, each filter optionally scoped to a location
- Atomic cross-run dedup at the database layer — safe to trigger a manual check anytime, even mid-scheduled-run
- Telegram digest notification the moment something new matches
- Runs every 15 minutes on a small always-on deployment — see [Deployment](#deployment)
- Every ingestion run (success or failure) is recorded with timestamps and aggregate counts; a per-source fetched/matched breakdown is logged and queryable via `GET /ingestion/runs` or the worker's application log
- Flutter dashboard for stored jobs, on-demand checks, and source/keyword configuration — runs on web, Windows, Android, and iOS, with an in-app, persisted backend-URL setting so a phone on the same Wi-Fi can reach a backend running on your PC (see [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#running-on-a-phone-androidios))
- Upload a PDF resume and Gemini extracts your skills, titles, years of experience, seniority, locations, and education — only the extracted data is kept, never the original file
- A "For You" tab ranks your ingested jobs by resume similarity (pgvector cosine distance over Gemini embeddings) — a re-ranking layer on top of your own keyword-filtered jobs, computed once per job at ingestion time, not per request
- Per-IP rate limiting on signup/login (open signup by default, so this is what actually protects the free Gemini quota and stops scripted account creation)

## Demo

See [bot_docs/README.md](bot_docs/README.md#screenshot) for a screenshot of the dashboard shell.

## Getting Started

### Prerequisites

- Python 3.12+
- Flutter SDK (only needed for the dashboard UI)
- A Telegram bot token ([@BotFather](https://t.me/BotFather)) — optional, but alerts don't send without it
- Optionally, a dedicated Gmail account + [App Password](https://myaccount.google.com/apppasswords) if you want LinkedIn/Naukri/Indeed alerts

### Installation

```bash
git clone https://github.com/OmNaphade/job-bot.git
cd job-bot/backend
docker compose up -d              # local Postgres+pgvector, see docker-compose.yml
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
copy .env.example .env
REM edit .env with real values, then apply the schema:
python -m alembic upgrade head
```

Notification channels (Telegram/Slack/Discord) aren't env vars — each account sets its own from **Settings → Notifications** in the app after signing up. Every other source (RSS/aggregator-API feeds, LinkedIn/Naukri/Indeed email alerts) has its own env vars with working defaults where a public feed exists — full reference in [bot_docs/SOURCES.md](bot_docs/SOURCES.md).

## Usage

### Backend

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

This serves the API only — it doesn't run ingestion itself (see [Deployment](#deployment) for what does). To trigger a pass locally: `python -m scripts.run_ingestion_once` (every due account) or `POST /ingest` (just yours, immediately). A couple of endpoints to try once it's up:

```bash
curl http://127.0.0.1:9000/health
curl -X POST http://127.0.0.1:9000/auth/signup -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "at-least-8-chars"}'
# use the returned token as: -H "Authorization: Bearer <token>"
```

### Frontend (dashboard + accounts)

```bash
cd frontend
flutter pub get
flutter run -d chrome    # or: flutter run -d windows
```

Points at `127.0.0.1:9000` by default; change it in-app via **Settings → Server connection** if your backend runs elsewhere (e.g. on a phone reaching your PC over LAN), then sign up or log in. Full instructions, including running on a real Android/iOS device, in [frontend/README.md](frontend/README.md) and [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#running-on-a-phone-androidios).

## Project Structure

```
.
├── backend/            # FastAPI service + ingestion pipeline (routes, services, repositories, adapters, Alembic migrations)
├── frontend/           # Flutter dashboard
├── deploy/             # OCI provisioning scripts (oci_deploy_app.sh for VM1, oci_deploy_db.sh for VM2)
├── bot_docs/           # architecture, API reference, source setup, deployment docs, screenshots
├── .github/workflows/  # CI (ci.yml) -- tests only, no scheduled workflow
└── README.md
```

## Documentation

Architecture, the full API reference, the ingestion flow, data model, per-source setup instructions, and deployment/testing details all live in **[bot_docs/](bot_docs/README.md)** rather than here, to keep this file a quick-start. Start at [bot_docs/README.md](bot_docs/README.md).

## Testing

```bash
cd backend && docker compose up -d && pytest -q
cd frontend && flutter analyze && flutter test
```

Backend tests run against a real Postgres+pgvector instance (no live network calls to job sources) with per-test transaction rollback isolation — safe anywhere, including CI. Coverage details in [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#testing).

## Deployment

The primary way to run this is **not** locally — it deploys to two small always-free OCI VMs (one running the API + nginx, one running Postgres + a systemd timer that ticks every 15 minutes), so it works with no dependency on any of your devices being online. Provisioning scripts and one-time setup steps are in [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#deploying-to-oci-2-vms).

## Roadmap

- [x] Validate the LinkedIn and Indeed email parsers against a real alert email — both now calibrated against real digests; Naukri's parser is still best-effort (no genuine job-match digest has been available to check it against yet, only newsletter content)
- [x] Use `preferences.location` in matching — a keyword filter can now be scoped to a location (`POST /preferences` with both `keyword` and `location`); bulk `POST /ingest/keywords` still applies unscoped
- [x] Surface ingestion run history in the Flutter dashboard — `run_history_screen.dart`, backed by `GET /ingestion/runs`
- [ ] Pull postings from public Telegram job-posting channels — needs a personal-account MTProto login (Telethon/Pyrogram), not just the bot API, plus a per-channel message parser; scoping, not started
- [ ] Shared/global job pool for matching, so one user's ingestion enriches everyone's candidate matches instead of each account only matching against jobs its own keyword filters already pulled in — needs splitting `jobs` into a shared postings table plus per-user visibility; real schema work, not started

## Security

No secrets are ever committed — `.env` is gitignored on every machine (local, VM1, VM2). If you find an actual vulnerability, please open an issue rather than a public PR with exploit details.

## License

No license file is set yet — treat this as all-rights-reserved for now.

## Contact

Om Naphade — [github.com/OmNaphade](https://github.com/OmNaphade)

Project repo: [github.com/OmNaphade/job-bot](https://github.com/OmNaphade/job-bot)
