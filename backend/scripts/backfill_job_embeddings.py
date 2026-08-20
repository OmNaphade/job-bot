"""One-off sweep to embed jobs that predate embedding-at-ingestion-time (e.g.
rows migrated from the legacy SQLite database, see
scripts/migrate_sqlite_to_postgres.py) or whose embed call failed and was
never retried.

Safe to re-run -- each pass only picks up rows still missing an embedding
(`WHERE embedding IS NULL`, see JobRepository.list_jobs_missing_embedding),
so a partial run just continues where it left off next time.

Run from the backend/ directory: `python -m scripts.backfill_job_embeddings`
"""

import logging

from app.db import database
from app.ingestion.services.embedding_service import EmbeddingService
from app.repositories.job_repository import JobRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def main() -> None:
    database.get_pool().wait()
    repository = JobRepository()
    embedding_service = EmbeddingService(repository=repository)

    total = 0
    succeeded = 0
    after_id = 0
    while True:
        jobs = repository.list_jobs_missing_embedding(after_id=after_id, limit=BATCH_SIZE)
        if not jobs:
            break
        embedding_service.embed_jobs(jobs)
        total += len(jobs)
        # Re-check which of this batch actually got an embedding -- embed_job()
        # swallows failures internally (see EmbeddingService), so this loop
        # can't tell success from failure any other way.
        still_missing = {job.id for job in repository.list_jobs_missing_embedding(after_id=after_id, limit=BATCH_SIZE)}
        succeeded += sum(1 for job in jobs if job.id not in still_missing)
        after_id = max(job.id for job in jobs)
        logger.info("Processed %d job(s) so far this run (%d embedded successfully)", total, succeeded)
        if len(jobs) < BATCH_SIZE:
            break

    logger.info("Backfill complete: %d job(s) processed, %d embedded successfully", total, succeeded)


if __name__ == "__main__":
    main()
