# Job Alert

[![CI](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/OmNaphade/job-bot/actions/workflows/ci.yml)

A Python script that checks job sources every 2 hours and sends new matches to your Telegram bot. No server, no
database, no app: a config file, a `.env` for secrets, and GitHub Actions (or Windows Task Scheduler) to run it.

```text
sources ──► filter + score ──► skip what you've already seen ──► Telegram
```

## What it does

- **Good results, not just many.** Drops senior titles, jobs asking for more experience than you have, wrong
  places and region-locked remote jobs. LinkedIn jobs are opened and their *description* is read, so experience
  and tech stack are checked for real. Titles like "Associate Engineer" or "Analyst" get in only when the
  description proves it is a Java/Spring/React/DevOps role.
- **Best first.** Each job is scored (keywords in the title, skills, boost words, your city, how new it is). Top
  matches arrive as their own message with an *Apply* button; the rest in a compact digest.
- **No repeats.** The same role seen on LinkedIn and Foundit is alerted once. If Telegram is down, unsent jobs are
  retried on the next run.
- **Quiet nights.** No checks or pings from 00:00 to 07:00 IST; the 07:17 run sends the overnight jobs.
- **Daily summary** at ~21:00 (checks run, jobs sent per source, anything failing) as proof it's alive.
- **Tells you when a source breaks** after 3 failed runs in a row.
- **A commit per run.** Each run commits its memory and a row in `runs.md` to the `state` branch, so the run history
  is visible on GitHub. `main` is never touched by the bot.

## Sources

| Source | Notes |
| --- | --- |
| LinkedIn search | Public logged-out search, no account. Throttled to about once an hour. |
| LinkedIn / Naukri / Indeed alert emails | Read from your Gmail over IMAP: the dependable way to get Naukri. |
| Foundit | Experience range, salary and skills included. About once an hour. |
| Unstop | Jobs and internships, strong for freshers. |
| Adzuna, Jooble | Free API keys (optional). |
| Company career pages | Greenhouse / Lever / Ashby: often the first place a role appears. |
| Remote job boards | WeWorkRemotely, Himalayas, Remotive, RemoteOK, Arbeitnow, Jobspresso, NoDesk. |
| Public Telegram channels | Add channel usernames in `config.yaml`. |

## Setup

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
.venv\Scripts\python -m jobalert test-telegram      # you should get a message
.venv\Scripts\python -m jobalert run --dry-run      # shows what would be sent, sends nothing
.venv\Scripts\python -m jobalert run                # the real thing
```

Telegram values: create a bot with [@BotFather](https://t.me/BotFather) for the token, message your bot once, then
open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
The first real run alerts on your best 10 matches and quietly remembers the rest, so you aren't flooded.

Everything you'd want to change (keywords, exclusions, places, experience cap, sources, quiet hours) is in
[config.yaml](config.yaml). `--only linkedin` limits a run to one source.

## Running it automatically

**GitHub Actions** (nothing needs to stay on): add your `.env` values as repository secrets and run the workflow
once from the Actions tab. After that it runs by itself every 2 hours at :17 India time. Full steps:
[docs/RUNBOOK.md](docs/RUNBOOK.md). `config.yaml` is committed, so on a public repo your searches and city are
visible; secrets are not.

**Windows Task Scheduler** (only while your PC is on):

```powershell
schtasks /Create /SC HOURLY /MO 2 /ST 07:17 /TN "JobAlert" /TR "D:\PRACTICE\job-alert\run.bat"
```

Use one scheduler, not both: they keep separate memories and you'd get duplicates.

## LinkedIn and Naukri

Neither offers a job feed and both fight bots, so, from most to least dependable:

1. **Saved-search emails.** On each site create a job alert that emails a Gmail account, make an
   [App Password](https://myaccount.google.com/apppasswords) for it, put it in `.env`. The `email_alerts` source
   turns those emails into alerts (LinkedIn ones are also opened and checked like search results). Nothing to block.
   Naukri's parser has not been tested against a real Naukri email yet; if `--only email --dry-run` logs *no jobs
   recognised in a naukri email*, that layout needs a tweak.
2. **LinkedIn search** (`linkedin` source): uses the public search page. Unofficial; LinkedIn throttles it and
   often blocks GitHub's servers. Works best from your own PC.
3. **Naukri directly:** not possible (its API answers `recaptcha required` to scripts).

### Will this get my accounts blocked?

The script never logs in to LinkedIn, Naukri, Foundit or Indeed, so there is no account for them to flag. The only
login is your own Gmail, read-only, with an app password. A site can still throttle or block the *IP address*
(a `429` in the log): temporary, not an account issue. To keep that unlikely: LinkedIn and Foundit are only
asked about once an hour, requests are spaced seconds apart, job pages are opened only for *new* jobs (capped and
time-boxed), and after two refused searches or three refused pages it stops asking for the rest of that run.
For zero exposure, set `linkedin.enabled` and `foundit.enabled` to `false` and rely on the email alerts.

## Project

```text
jobalert/            the package (pipeline, filters, notify, store, sources/)
config.yaml          what you want
tests/               pytest, no network
docs/                ARCHITECTURE.md, RUNBOOK.md
.github/workflows/   ci.yml, jobalert.yml (production schedule), release.yml
```

Development follows `feature/*` → `develop` → `main` (production); see [CONTRIBUTING.md](CONTRIBUTING.md).
Changes are listed in [CHANGELOG.md](CHANGELOG.md). Security notes: [SECURITY.md](SECURITY.md).

## Troubleshooting

- **`IMAP login failed`**: the Gmail App Password is wrong or revoked; create a new one.
- **`linkedin ... 429`**: LinkedIn is throttling you; the run carries on without it.
- **Nothing arrives**: run with `--dry-run`; the *filtered out* line shows which rule removes jobs.
- **Re-send everything**: delete `data/state.json` locally, or the `state` branch on GitHub.
