from typing import List, Optional

from app.db.database import db_session
from app.models.ingestion_run import IngestionRun


class IngestionRunRepository:
    def record(self, user_id: int, run: IngestionRun) -> IngestionRun:
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ingestion_runs
                    (user_id, started_at, finished_at, status, fetched_count, matched_count, new_count, delivered_count, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
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

    def list_recent(self, user_id: int, limit: int = 20) -> List[IngestionRun]:
        with db_session() as connection:
            rows = connection.execute(
                """
                SELECT id, started_at, finished_at, status, fetched_count, matched_count, new_count, delivered_count, error_message
                FROM ingestion_runs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [IngestionRun(**dict(row)) for row in rows]

    def most_recent_finished_at(self, user_id: int) -> Optional[str]:
        """The `finished_at` of this user's most recent run, or None if they've
        never had one -- used by the scheduler to decide if they're due for
        another pass yet, per their own `poll_interval_hours`."""
        with db_session() as connection:
            row = connection.execute(
                "SELECT finished_at FROM ingestion_runs WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
        return row["finished_at"] if row else None
