# Changelog

All notable changes to this project. Format follows [Keep a Changelog](https://keepachangelog.com),
versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- Run log: every run (quiet ones too) appends a row to `runs.md` and commits it with the saved state to the
  `state` branch, so GitHub shows one commit per run: time, link to the Actions run, how long it took, jobs fetched/new/sent
  and any failing sources.

## [2.0.0] - 2026-10-13

First release of the script-only rewrite.

### Added
- Telegram alerts: best matches as individual messages with an Apply button, the rest in a compact digest.
- Sources: LinkedIn search, LinkedIn/Naukri/Indeed alert emails (IMAP), Foundit, Unstop, Adzuna, Jooble,
  remote job boards, Greenhouse/Lever/Ashby company boards, public Telegram channels.
- LinkedIn job pages are read to check required experience and tech stack before alerting.
- Generic titles ("Associate Engineer", "Analyst", ...) accepted only when the description shows a tech role.
- Filters: include/exclude keywords, location, age, maximum experience, company block/prefer lists,
  region-locked remote postings, minimum salary. Skills list for ranking.
- Quiet hours (00:00-07:00 IST by default) and a daily summary message.
- Cross-source de-duplication, retry of undelivered alerts, warnings when a source keeps failing.
- Per-source throttling and early stop when a site refuses requests.
- Scheduled GitHub Actions run every 2 hours (07:17 to 05:17 IST); manual runs from other branches are dry-runs.
- CI (ruff + pytest), release workflow, Dependabot, pull request and issue templates.

### Removed
- The Flutter app, FastAPI backend, Postgres storage, accounts, resume matching and OCI deployment scripts.
