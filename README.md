# Job Alert

A small Python script that checks job sources on a schedule and sends new matches to your Telegram bot. No server, no database, no app: a config file, a `.env` for secrets, and a scheduler (GitHub Actions or Windows Task Scheduler).

```
sources ──► filter + score ──► dedupe against state.json ──► Telegram
```

- **Fresh only.** Jobs older than 3 days, senior titles, jobs asking for more experience than you have, and wrong locations are dropped.
- **Best first.** Each job gets a score (keyword hits in the title, boost words, your city, how new it is). Top matches arrive as their own message with an *Apply* button; the rest as a compact digest.
- **No repeats.** The same role seen on LinkedIn and Foundit is alerted once. If Telegram is down, unsent jobs are retried next run.
- **Tells you when a source breaks.** After 4 failed runs in a row you get one Telegram warning.

## Setup (5 minutes)

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env          # then fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
.venv\Scripts\python -m jobalert test-telegram      # you should get a message
.venv\Scripts\python -m jobalert run --dry-run      # shows what would be sent, sends nothing
.venv\Scripts\python -m jobalert run                # the real thing
```

Getting the Telegram values: create a bot with [@BotFather](https://t.me/BotFather) for the token, message your bot once, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.

The first real run alerts on your best 10 matches and quietly remembers the rest, so you aren't flooded.

## Tuning

Everything you'd want to change is in [config.yaml](config.yaml): keywords, exclusions, locations, experience cap, which sources are on, LinkedIn searches, Foundit queries, company boards. Run `--dry-run` after editing to see the effect. `--only linkedin` limits a run to one source.

## Running it automatically

**GitHub Actions (nothing needs to stay on).** Push this repo, then add the secrets from `.env` under *Settings → Secrets and variables → Actions* (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `JOOBLE_API_KEY`). [jobalert.yml](.github/workflows/jobalert.yml) runs at :17 and :47 past every hour (off the busy :00/:30 marks, which GitHub delays) and keeps its memory on a `state` branch. Start it once from the *Actions* tab with *Run workflow*.

Note that `config.yaml` is committed, so on a public repo your search terms and city are visible, and so are the job links on the `state` branch. Secrets are not: they live only in GitHub's encrypted secrets and your local `.env`.

**Windows Task Scheduler (runs while your PC is on).** From an admin prompt:

```powershell
schtasks /Create /SC MINUTE /MO 30 /TN "JobAlert" /TR "D:\PRACTICE\job-alert\run.bat"
```

Output is appended to `data\run.log`. Run only one of the two schedulers: they keep separate memories and you'd get duplicates.

## Getting LinkedIn and Naukri jobs

Neither site offers a job feed, and both fight bots, so there are three routes, from most to least dependable:

1. **Saved-search emails (recommended for both).** On each site, create a job alert and set it to email you (LinkedIn: search → *Set alert*; Naukri: *Create job alert* on any search). Point them at a Gmail account, make an [App Password](https://myaccount.google.com/apppasswords), and put it in `.env`. The `email_alerts` source reads those emails over IMAP and turns them into Telegram alerts. This uses the sites' own alert feature, so there is nothing to block. If a Gmail filter files the emails under a label, add the label under `mailboxes` in `config.yaml` (and tick *Show in IMAP* for it in Gmail's label settings).
   - LinkedIn and Indeed email layouts were checked against real emails. **Naukri's parser has never seen a real job-alert email**, so treat it as unproven: run `python -m jobalert run --only email --dry-run`, and if it logs *no jobs recognised in a naukri email*, that email's layout needs a parser tweak.
2. **LinkedIn search (`linkedin` source).** Uses the public, logged-out search endpoint with your keywords, locations and experience level, and returns jobs posted in the last 24 hours with their real posting time. It is unofficial: LinkedIn rate-limits it (the script waits and retries) and often blocks GitHub's servers entirely. It works best from your own PC via Task Scheduler. If it is blocked, you get the failure warning and route 1 still covers LinkedIn.
3. **Naukri directly: not possible.** Its search API answers `recaptcha required` to scripts. Use route 1.

Other sources that are reliable today and cover a lot of the same ground: **Foundit** (also gives experience and salary), **Unstop**, company career pages (Greenhouse/Lever/Ashby, which often list a role before any job board), Adzuna/Jooble (free keys), and public Telegram job channels (add usernames under `telegram_channels`).

## Will this get my accounts blocked?

The script never logs in to LinkedIn, Naukri, Foundit or Indeed, so there is no account on those sites for them to flag. The only login anywhere is your own Gmail inbox, read-only over IMAP with an app password, which is a normal supported use.

What a site *can* do to a logged-out client is throttle or block its IP address (you'll see `429` in the log). It is temporary and doesn't touch your account, but it can briefly affect that site in your own browser too. The script is built to stay light:

- LinkedIn is searched at most once an hour and Foundit once an hour (`min_interval_minutes`), however often the scheduler fires.
- Requests are spaced seconds apart, and LinkedIn job pages are opened only for *new* jobs, capped per run and by a time budget.
- After two refused searches in a row, or three refused job pages, it stops asking for the rest of that run.
- Naukri is never contacted at all; it only arrives through the alert emails Naukri sends you.

For zero exposure, set `linkedin.enabled: false` and `foundit.enabled: false` in `config.yaml` and rely on the email alerts. You lose speed and coverage, but nothing touches those sites except you.

## Layout

```
jobalert/
  __main__.py        CLI: run [--dry-run] [--only X], test-telegram
  pipeline.py        fetch all sources -> filter -> dedupe -> send -> save state
  filters.py         include/exclude/location/age/experience rules and scoring
  notify.py          Telegram messages
  store.py           state.json (what's been alerted, source failure counts)
  sources/           one small module per source
config.yaml          what you want
tests/               pytest, no network
```

Tests: `pytest -q`.

## Troubleshooting

- **`IMAP login failed ... AUTHENTICATIONFAILED`**: the Gmail App Password is wrong or revoked. Create a new one, and make sure IMAP is enabled in Gmail settings.
- **`linkedin ... 429`**: LinkedIn is throttling you. Fewer `searches`, `pages: 1`, or run from your own PC instead of GitHub.
- **Nothing arrives**: run with `--dry-run`; the *filtered out* line shows which rule is removing jobs (`too old`, `location`, `excluded keyword`, ...).
- **Want to re-send everything**: delete `data/state.json` (or the `state` branch on GitHub).
