# Contributing

## Branches

| Branch | Purpose | Who writes to it |
| --- | --- | --- |
| `main` | **Production.** The scheduled GitHub Actions run executes whatever is on `main`. | Release merges from `develop` only. |
| `develop` | Integration. Everything lands here first and is tried against live sources before release. | Feature/fix branches via pull request. |
| `feature/*`, `fix/*` | One change each, branched from `develop`. | You. |
| `state` | Machine-written memory of what was already alerted, plus `runs.md` (one row and one commit per run). Never merge it. | The workflow. |

```text
feature/x ──PR──► develop ──PR (release)──► main ──tag vX.Y.Z──► GitHub Release
```

## Making a change

```powershell
git checkout develop && git pull
git checkout -b feature/short-name

# set up once
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt

# before every push
.venv\Scripts\ruff check .
.venv\Scripts\python -m pytest
.venv\Scripts\python -m jobalert run --dry-run     # live sources, sends nothing, saves nothing
```

Open a pull request into `develop`. CI must pass (lint + tests on Python 3.12 and 3.13). Add a line to
**Unreleased** in [CHANGELOG.md](CHANGELOG.md).

Trying a change on GitHub before release: Actions → *Job alert (production)* → *Run workflow* → pick your
branch. Any branch other than `main` is forced into dry-run, so it can't message you or touch the saved state.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org): `feat: ...`, `fix: ...`, `config: ...`,
`docs: ...`, `chore: ...`, `ci: ...`, `test: ...`. Imperative, under 72 characters for the subject, and say
*why* in the body when it isn't obvious.

## Releasing

1. Move **Unreleased** in the changelog under a new `## [X.Y.Z] - date` heading and bump `__version__` in
   `jobalert/__init__.py` (SemVer: new behavior = minor, fixes = patch, breaking config change = major).
2. Pull request `develop` → `main`, merge with a merge commit (not squash, so the history stays traceable).
3. Tag the merge: `git tag vX.Y.Z && git push origin vX.Y.Z`. The release workflow publishes the GitHub Release.

Rollback: revert the merge commit on `main` (or re-run the previous tag); the next scheduled run uses it.

## Branch protection (set once in GitHub → Settings → Branches)

- `main`: require a pull request, require the **CI** checks, no force pushes, no deletions.
- `develop`: require the **CI** checks, no force pushes.

## Code conventions

- Each source is one small class in `jobalert/sources/` that returns `Job` objects or raises `FetchError`.
  It must never log in to a job site, and it must keep request volume low (see `min_interval_minutes`).
- Filtering and scoring live in `filters.py`, orchestration in `pipeline.py`. Sources do not filter.
- Tests run without network. Parsers get a small saved HTML/JSON sample rather than a live call.
- No secrets, tokens or personal data in commits. Secrets live in `.env` locally and in repository secrets on GitHub.
