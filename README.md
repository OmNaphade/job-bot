# Job Alert Platform

A continuously-running job-monitoring bot with a FastAPI backend and a Flutter dashboard. It polls job sources on a schedule, matches new postings against your saved keyword preferences, and pushes a Telegram alert the moment something new matches — without you needing to open the app.

[![CI](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml)
[![Scheduled ingestion](https://github.com/OmNaphade/job-bot/actions/workflows/ingest.yml/badge.svg)](https://github.com/OmNaphade/job-bot/actions/workflows/ingest.yml)

## Table of Contents

- [About](#about)
- [Built With](#built-with)
- [Features](#features)
- [Demo](#demo)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Testing](#testing)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Security](#security)
- [License](#license)
- [Contact](#contact)

## About

Job hunting means checking the same handful of boards over and over. This runs the checking for you: an ingestion pipeline fetches candidate postings from several remote-job RSS/JSON feeds plus your own LinkedIn/Naukri saved-search email alerts, filters them against include/exclude keywords you set, drops anything already seen, and sends a Telegram digest for what's actually new. It's designed to never scrape LinkedIn/Naukri directly — those two go through your own email alerts instead, everything else uses feeds meant for exactly this kind of consumption.

It runs unattended via a scheduled GitHub Actions workflow (hourly), so it doesn't depend on a laptop staying on. The Flutter app is an optional dashboard on top, not a requirement for the bot to function.

## Built With

- Python 3.12 / FastAPI (backend API)
- APScheduler (background polling for local/always-on runs)
- SQLite, single-file, committed to git as the durable state store
- Flutter / Material 3 (dashboard UI)
- `feedparser` + `requests` (RSS/JSON source adapters)
- GitHub Actions (hourly scheduled ingestion runner + CI)

## Features

- Polls 6 verified RSS/JSON remote-job feeds (WeWorkRemotely, Himalayas, Remotive, NoDesk, Jobspresso, RemoteOK) with no scraping involved
- LinkedIn/Naukri support via your own saved-search email alerts (IMAP), never talks to linkedin.com/naukri.com directly
- Include/exclude keyword matching against title/company/location
- Atomic cross-run dedup at the database layer — safe to trigger a manual check anytime, even mid-scheduled-run
- Telegram digest notification the moment something new matches
- Runs hourly on GitHub's infrastructure — no server or always-on machine required
- Every ingestion run (success or failure) is recorded with timestamps, counts, and error detail
- Flutter dashboard for stored jobs, on-demand checks, and source/keyword configuration

## Demo

See [bot_docs/README.md](bot_docs/README.md#screenshot) for a screenshot of the dashboard shell.

## Getting Started

### Prerequisites

- Python 3.12+
- Flutter SDK (only needed for the dashboard UI)
- A Telegram bot token ([@BotFather](https://t.me/BotFather)) — optional, but alerts don't send without it
- Optionally, a dedicated Gmail account + [App Password](https://myaccount.google.com/apppasswords) if you want LinkedIn/Naukri alerts

### Installation

```bash
git clone https://github.com/OmNaphade/job-bot.git
cd job-bot/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
copy .env.example .env
REM edit .env with real values
```

| Variable | Description | Default |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | — |
| `TELEGRAM_CHAT_ID` | Chat id to send alerts to | — |

Every other source (RSS feeds, LinkedIn/Naukri email alerts) has its own env vars with working defaults where a public feed exists — full reference in [bot_docs/SOURCES.md](bot_docs/SOURCES.md).

## Usage

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 9000
```

The scheduler starts automatically with the app and polls on its own from then on. A couple of endpoints to try once it's up:

```bash
curl http://127.0.0.1:9000/health
curl -X POST http://127.0.0.1:9000/ingest
```

## Project Structure

```
.
├── backend/            # FastAPI service + ingestion pipeline (routes, services, repositories, adapters)
├── frontend/           # Flutter dashboard
├── bot_docs/           # architecture, API reference, source setup, deployment docs, screenshots
├── .github/workflows/  # CI (ci.yml) + scheduled ingestion cron (ingest.yml)
└── README.md
```

## Documentation

Architecture, the full API reference, the ingestion flow, data model, per-source setup instructions, and deployment/testing details all live in **[bot_docs/](bot_docs/README.md)** rather than here, to keep this file a quick-start. Start at [bot_docs/README.md](bot_docs/README.md).

## Testing

```bash
cd backend && pytest -q
cd frontend && flutter analyze && flutter test
```

Backend tests run against a temp SQLite DB with no live network calls — safe anywhere, including CI. Coverage details in [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#testing).

## Deployment

The primary way to run this is **not** locally — `.github/workflows/ingest.yml` runs one ingestion pass every hour on GitHub's own infrastructure, so the bot works with zero servers and no dependency on any of your devices being online. One-time secret/permission setup is in [bot_docs/OPERATIONS.md](bot_docs/OPERATIONS.md#deploying-github-actions-as-the-always-on-runner).

## Roadmap

- [ ] Wire in Unstop/Foundit once a real JSON endpoint is found (both render listings client-side; needs manual DevTools discovery)
- [ ] Validate the LinkedIn/Naukri email parsers against a real alert email (written against known structure, untested live)
- [ ] Use `preferences.location` in matching (currently stored but unused)
- [ ] Surface ingestion run history in the Flutter dashboard (`GET /ingestion/runs` already exists, just no UI for it yet)

## Security

No secrets are ever committed — `.env` is gitignored, and GitHub Actions secrets are encrypted at rest. If you find an actual vulnerability, please open an issue rather than a public PR with exploit details.

## License

No license file is set yet — treat this as all-rights-reserved for now.

## Contact

Om Naphade — [github.com/OmNaphade](https://github.com/OmNaphade)

Project repo: [github.com/OmNaphade/job-bot](https://github.com/OmNaphade/job-bot)
