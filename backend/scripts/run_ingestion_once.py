"""Entrypoint for a single ingestion pass, meant for the scheduled GitHub Actions
runner (see .github/workflows/ingest.yml) -- a short-lived process that fetches,
matches, dedupes, persists, and notifies once, then exits.

Run from the `backend/` directory: `python -m scripts.run_ingestion_once`
"""

import logging
import os

from app.db.database import init_db
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
    init_db()
    logger = logging.getLogger(__name__)

    try:
        result = IngestionService().run()
    except Exception as exc:
        logger.exception("Ingestion run failed")
        _write_step_summary(f"### Ingestion run failed\n\n```\n{exc}\n```\n\nEvery run (success or failure) is also recorded in `ingestion_runs` -- see `GET /ingestion/runs`.")
        raise

    logger.info("Ingestion run result: %s", result)
    _write_step_summary(
        "### Ingestion run succeeded\n\n"
        f"- Fetched: {result['fetched']}\n"
        f"- Matched: {result['matched']}\n"
        f"- New: {result['new']}\n"
        f"- Delivered to Telegram: {result['delivered']}\n"
    )


if __name__ == "__main__":
    main()
