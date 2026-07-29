"""Entrypoint for a single ingestion pass, meant for the scheduled GitHub Actions
runner (see .github/workflows/ingest.yml) -- a short-lived process that fetches,
matches, dedupes, persists, and notifies once, then exits.

Run from the `backend/` directory: `python -m scripts.run_ingestion_once`
"""

import logging

from app.db.database import init_db
from app.ingestion.services.ingestion_service import IngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    init_db()
    result = IngestionService().run()
    logging.getLogger(__name__).info("Ingestion run result: %s", result)


if __name__ == "__main__":
    main()
