# Runbook

## Schedule

Production runs from `main` every 2 hours at **:17 India time** (cron `47 1-23/2 * * *`, UTC):
07:17, 09:17, 11:17, 13:17, 15:17, 17:17, 19:17, 21:17, 23:17, 01:17, 03:17, 05:17.
Quiet hours (00:00-07:00 IST) skip 01:17, 03:17 and 05:17, so about 9 real checks a day, and the 07:17 run
delivers the overnight jobs. The 21:17 run also sends the daily summary. GitHub can start a scheduled run a few
minutes late; that is normal.

## First-time setup

1. Repository → Settings → Secrets and variables → Actions: add `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and
   optionally `ALERT_EMAIL_ADDRESS`, `ALERT_EMAIL_APP_PASSWORD`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`,
   `JOOBLE_API_KEY`.
2. Actions → *Job alert (production)* → *Run workflow* on `main` (leave *dry run* off) for the first real run.
3. Settings → Branches: protect `main` and `develop` (see CONTRIBUTING.md).

Until the Telegram secrets exist, the scheduled run does nothing and shows a warning instead of failing.

## Where to look when something is wrong

| Symptom | Look at | Likely cause / fix |
| --- | --- | --- |
| No alerts for a day | Actions run page → job summary table | Everything filtered out (see the "filtered out" line), or a source failing |
| `FAILED: ... 429` on linkedin | Run log | LinkedIn throttling GitHub's IP. Alert emails still cover LinkedIn. Not an account problem. |
| `IMAP login failed` | Run log | Gmail app password revoked or mistyped: create a new one, update the secret |
| Telegram message "⚠️ X has failed 3 runs" | The message | Source changed or is blocked; check its row in the job summary |
| Same job alerted twice | `state` branch | State was lost (first-run behavior) or two schedulers are running. Run only one. |
| Workflow not running | Actions tab | GitHub pauses schedules after 60 days with no repo activity: click *Enable workflow* |

## Common operations

- **Try a change safely:** push your branch, Actions → *Run workflow* → select the branch. Non-`main` branches are
  dry-runs.
- **Run locally without sending:** `python -m jobalert run --dry-run`; one source: add `--only foundit`.
- **Reset memory:** delete the `state` branch on GitHub (and `data/state.json` locally). Next run is a first run
  and sends only the best 10.
- **Pause alerts:** Actions → the workflow → ⋯ → *Disable workflow*.
- **Rotate a secret:** see SECURITY.md.
- **Roll back a release:** revert the merge commit on `main`; the next run uses the reverted code.
