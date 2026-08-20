"""Entrypoint for a single multi-user ingestion pass, meant for the scheduled
GitHub Actions runner (see .github/workflows/ingest.yml) -- a short-lived
process that runs one pass per user (skipping anyone not yet due per their own
poll_interval_hours), then exits.

Run from the `backend/` directory: `python -m scripts.run_ingestion_once`
"""

import logging
import os

from app.db import database
from app.ingestion.services.ingestion_service import IngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _write_step_summary(markdown: str) -> None:
    # GITHUB_STEP_SUMMARY is only set inside a GitHub Actions run; a no-op locally.
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write(markdown + "\n")


def main() -> None:
    # Schema is applied by `alembic upgrade head` as its own deploy step (see
    # deploy/oci_deploy_db.sh), not here -- this just fails fast if the DB is
    # unreachable rather than partway through the first query.
    database.get_pool().wait()
    logger = logging.getLogger(__name__)

    try:
        result = IngestionService().run_all_users()
    except Exception as exc:
        logger.exception("Ingestion run failed")
        _write_step_summary(f"### Ingestion run failed\n\n```\n{exc}\n```\n\nEvery per-user run (success or failure) is also recorded in `ingestion_runs` -- see `GET /ingestion/runs`.")
        raise

    logger.info("Ingestion run result: %s", result)

    user_rows = "\n".join(
        f"| {run['user_id']} | {run['fetched']} | {run['matched']} | {run['new']} | {run['delivered']} |"
        for run in result["per_user"]
    )
    _write_step_summary(
        "### Ingestion run succeeded\n\n"
        f"- Users run: {result['users_run']}\n"
        f"- Total fetched: {result['total_fetched']}\n"
        f"- Total matched: {result['total_matched']}\n"
        f"- Total new: {result['total_new']}\n"
        f"- Total delivered: {result['total_delivered']}\n\n"
        "| User ID | Fetched | Matched | New | Delivered |\n"
        "|---|---|---|---|---|\n"
        f"{user_rows}\n"
    )


if __name__ == "__main__":
    main()
