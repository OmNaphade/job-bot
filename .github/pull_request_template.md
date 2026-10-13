## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Type

- [ ] feat (new behavior)
- [ ] fix (bug fix)
- [ ] config (config.yaml defaults only)
- [ ] chore / docs / ci

## Checklist

- [ ] `ruff check .` and `pytest` pass locally
- [ ] Tests added or updated for the change
- [ ] `python -m jobalert run --dry-run` still looks right against live sources
- [ ] `CHANGELOG.md` updated under **Unreleased**
- [ ] No secrets, tokens or personal data in the diff
- [ ] Target branch is `develop` (only release PRs go to `main`)
