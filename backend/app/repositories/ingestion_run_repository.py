from typing import List

from app.db.database import db_session
from app.models.ingestion_run import IngestionRun


class IngestionRunRepository:
    def record(self, run: IngestionRun) -> IngestionRun:
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs
                    (started_at, finished_at, status, fetched_count, matched_count, new_count, delivered_count, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.started_at,
                    run.finished_at,
                    run.status,
                    run.fetched_count,
                    run.matched_count,
                    run.new_count,
                    run.delivered_count,
                    run.error_message,
                ),
            )
            run_id = cursor.lastrowid
        return run.model_copy(update={"id": run_id})

    def list_recent(self, limit: int = 20) -> List[IngestionRun]:
        with db_session() as connection:
            rows = connection.execute(
                """
                SELECT id, started_at, finished_at, status, fetched_count, matched_count, new_count, delivered_count, error_message
                FROM ingestion_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [IngestionRun(**dict(row)) for row in rows]
