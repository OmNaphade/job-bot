# Architecture

```text
            ┌────────────── sources/ ──────────────┐
 config.yaml│ linkedin  email_alerts  foundit  ...  │
     │      └───────────────┬───────────────────────┘
     │                      │ list[Job]  (fetched in parallel)
     ▼                      ▼
 filters.py ◄──── pipeline.py ────► notify.py ──► Telegram
 (rules+score)      │      ▲
                    ▼      │
                 store.py (state.json: seen jobs, failures, stats, last fetch)
```

## One run, step by step (`pipeline.run`)

1. **Quiet hours?** Between 00:00 and 07:00 IST the run exits at once; whatever appeared meanwhile is sent by
   the first run afterwards. Manual runs, `--only` and `--dry-run` ignore this.
2. **Load state** (`data/state.json`). No state yet = *first run*: alert on the best 10, quietly remember the rest.
3. **Pick sources that are due.** Throttled sources (LinkedIn, Foundit) sit out runs that come too soon after
   their last fetch.
4. **Fetch all due sources in parallel.** A source that raises is recorded as failed; the others carry on.
5. **Cheap filters** per job: already seen? too old? excluded title/company? wrong place or region-locked?
   too much experience? below minimum salary? no include keyword?
6. **Read job pages** for thin sources (LinkedIn search results and LinkedIn alert emails): open each survivor's
   public page, take the description and the experience it asks for, then judge it on that. Capped per run and
   by a time budget; stops early if the site refuses requests. Rejections are remembered so a page isn't
   opened twice.
7. **Score and sort** (title keyword hits, boost words, skills, preferred city/company, freshness).
8. **Send** to Telegram: top N individually, the rest as a digest. Only jobs that were actually delivered are
   marked seen, so a Telegram outage means a retry next run, not lost alerts.
9. **Housekeeping:** failure streaks (one warning after 3 failed runs), daily stats, the daily summary, save state.

## Why filters live in one place

Sources only translate a site's format into `Job`. All opinions (what is relevant, what is too senior) are in
`filters.py` and `config.yaml`, so adding a source never changes what you get alerted on, and tuning a filter
never touches network code.

## What "generic title" means

A title like *Associate Engineer* names no technology. It is accepted only if it matches `generic_titles` AND the
description or skills list contains at least `min_tech_evidence` matches from `include` + `skills`, at least one
of them an `include` term. So the Java *Associate Engineer* gets in and the *Business Analyst* does not.

## State

On GitHub the `state` branch also holds `runs.md`, a table with one row per run (written by `runlog.py`, trimmed
to the last 300 rows), so each run produces exactly one commit there.

`state.json` holds: `seen` (link and title|company|city fingerprints, pruned after 45 days), `failures`,
`alerted`, `last_fetch`, today's `stats`, and `initialized`. On GitHub it lives on the `state` branch, restored
before each run and pushed after it. Delete it to start over (the next run is a "first run" again).
