from datetime import datetime, timezone
from typing import Iterable, Set

from app.db import database


class ProcessedAlertEmailRepository:
    """Tracks which alert emails an EmailAdapter has already turned into candidates.

    Deliberately independent of IMAP's own \\Seen flag -- a Gmail filter with
    "mark as read" as one of its actions (or the user simply reading their own
    mail) marks a message seen before the bot ever polls it, which would make an
    IMAP UNSEEN search silently skip it forever. Message-ID is stable and only
    ever set by this repository, so it isn't affected by anything else touching
    the mailbox.

    Scoped by user_id: the underlying mailbox is shared config, but "have I
    already turned this message into a candidate" must be tracked per user --
    otherwise, if two users both enable e.g. LinkedIn alerts against the same
    mailbox, the first user's ingestion pass would mark the message processed
    and the second user's pass would silently never see it.
    """

    def filter_new(self, user_id: int, source: str, message_ids: Iterable[str]) -> Set[str]:
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return set()
        placeholders = ",".join("%s" for _ in ids)
        with database.db_session() as connection:
            rows = connection.execute(
                f"SELECT message_id FROM processed_alert_emails "
                f"WHERE user_id = %s AND source = %s AND message_id IN ({placeholders})",
                (user_id, source, *ids),
            ).fetchall()
        already_processed = {row["message_id"] for row in rows}
        return {message_id for message_id in ids if message_id not in already_processed}

    def mark_processed(self, user_id: int, source: str, message_ids: Iterable[str]) -> None:
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return
        now = datetime.now(timezone.utc)
        with database.db_session() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO processed_alert_emails (message_id, source, user_id, processed_at) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (message_id, source, user_id) DO NOTHING",
                    [(message_id, source, user_id, now) for message_id in ids],
                )
