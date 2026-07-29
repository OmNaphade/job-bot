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

The scheduler starts automatically with the app — as long as this process is running, it polls every `poll_interval_hours` and alerts on new matches with no further interaction. This assumes the process itself stays up (e.g. via a terminal left open, a Windows service, or Task Scheduler).

### Frontend

```bash
cd frontend
flutter pub get
flutter run -d chrome    # or: flutter run -d windows
```

The Flutter app always talks to `127.0.0.1:9000` — it only works while the backend above is running locally. It's a dashboard/config UI, not required for the bot itself to function (see below).

## Deploying: GitHub Actions as the always-on runner

Running the FastAPI app locally means the bot only polls while your machine is on. `.github/workflows/ingest.yml` avoids that entirely: a scheduled GitHub Actions workflow runs one ingestion pass every hour (`cron: "0 * * * *"`, 24 runs/day) on GitHub's infrastructure, with no server of your own required. State (seen jobs, ingestion settings, saved keywords, run history) lives in `backend/job_alert.db`, which the workflow commits back to the repo after every run — this is why `job_alert.db` is intentionally tracked in git rather than ignored.

The schedule runs entirely on GitHub's servers — it's unaffected by whether any of your own devices are online.

Two caveats:
- GitHub doesn't guarantee exact cron timing under load — runs can be delayed by minutes, or occasionally skipped; there's no backfill.
- GitHub auto-disables scheduled workflows after 60 days with zero commits to the repo. An active job hunt keeps this alive naturally (matches get committed), but if it goes fully quiet for 60 days the schedule stops until a commit or manual re-enable.

If the repo is ever made **private**, note that Actions minutes stop being unlimited-free and start counting against the account's monthly quota (2,000 min/month on GitHub's Free plan) — check actual run duration in the Actions tab before switching visibility.

### One-time setup

1. **Add repository secrets** (Settings → Secrets and variables → Actions → New repository secret) — same names as the `.env` variables (see [SOURCES.md](SOURCES.md)), added one at a time since there's no way to bulk-import from a script:
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (required for alerts)
   - `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD` (if using LinkedIn/Naukri email alerts)
   - Optionally: `ALERT_EMAIL_IMAP_HOST`, `ALERT_EMAIL_IMAP_PORT`, `LINKEDIN_ALERT_SENDER`, `NAUKRI_ALERT_SENDER`, and any of the RSS/JSON feed URL overrides
2. **Allow the workflow to push**: Settings → Actions → General → Workflow permissions → "Read and write permissions". Without this, the DB commit-back step fails (the ingestion itself still runs fine, but state won't persist between runs).
3. **Enable/tune settings and keywords once**, either by editing `backend/job_alert.db` via a local run, or by running the local backend, changing things through the Flutter app or API, then committing the resulting `job_alert.db`.
4. Trigger it once manually via the **Actions** tab → "Scheduled ingestion" → "Run workflow" to confirm it works before waiting for the first scheduled run.

### Run history / logs

Every run — success or failure, scheduled or manual — is recorded as a row in the `ingestion_runs` table, which lives in `job_alert.db` and gets committed back to the repo like everything else. Two ways to see it:

- **`GET /ingestion/runs`** — query the persisted history (timestamps, counts, error message if it failed) from the API/Flutter app.
- **GitHub Actions run summary** — each scheduled run also writes a short markdown summary (fetched/matched/new/delivered counts, or the error) directly to that run's page under the **Actions** tab, no DB query needed. Click into any past run → the "Summary" tab.

The commit-back step runs even when ingestion itself fails (`if: always()` in `ingest.yml`), so a failed run's history is pushed to the repo too, not just successful ones — and the workflow step itself still exits non-zero on failure, which is what drives GitHub's own "workflow run failed" email notification to repo watchers.

### Don't run both at once

The local FastAPI scheduler and the GitHub Actions cron runner each operate on their own copy of `job_alert.db` — they don't share state in real time, only whenever you `git pull`/`git push`. If you leave the local server running continuously *and* have the Actions workflow enabled, both will independently detect the same new postings and **you'll get duplicate Telegram alerts**. Pick one as the primary runner:

- **Actions as primary (recommended, matches "no laptop dependency")**: don't leave the local backend running unattended. Use it only for occasional dashboard/config sessions — `git pull` first, make your changes, `git push` after, so the next scheduled run picks them up.
- **Local as primary**: keep the Actions workflow disabled (Actions tab → "Scheduled ingestion" → "···" → Disable workflow), and run the FastAPI backend continuously instead.

## Testing

Backend (pytest, no live network calls — safe to run anywhere, including CI):

```bash
cd backend
pip install -r requirements.txt
pytest -q
```

Covers `matcher_service`, `dedup_service`, `email_parsers` (against hand-built sample HTML), the RSS/RemoteOK adapters, and repository-level duplicate/conflict handling (`job_repository`, `preference_repository`, `ingestion_settings_repository`, `ingestion_run_repository`) against a temp SQLite DB.

Frontend:

```bash
cd frontend
flutter analyze
flutter test
```

## CI/CD

Two separate workflows, deliberately not combined:

- **`.github/workflows/ci.yml`** — runs on every push/PR to `main`. Backend job installs `requirements.txt`, byte-compiles the app (`python -m compileall`), runs `pytest -q`. Frontend job runs `flutter pub get`, `flutter analyze`, `flutter test`. Self-contained — no secrets, no live network calls required to pass. A red run means an actual regression. Commits made by the ingestion workflow include `[skip ci]` so a routine DB update doesn't re-trigger the whole test suite.
- **`.github/workflows/ingest.yml`** — the scheduled cron runner described above. Needs the repository secrets and write permissions set up once (see "One-time setup").
