from datetime import datetime, timezone
from typing import Iterable, Set

from app.db.database import db_session


class ProcessedAlertEmailRepository:
    """Tracks which alert emails an EmailAdapter has already turned into candidates.

    Deliberately independent of IMAP's own \\Seen flag -- a Gmail filter with
    "mark as read" as one of its actions (or the user simply reading their own
    mail) marks a message seen before the bot ever polls it, which would make an
    IMAP UNSEEN search silently skip it forever. Message-ID is stable and only
    ever set by this repository, so it isn't affected by anything else touching
    the mailbox.
    """

    def filter_new(self, source: str, message_ids: Iterable[str]) -> Set[str]:
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return set()
        placeholders = ",".join("?" for _ in ids)
        with db_session() as connection:
            rows = connection.execute(
                f"SELECT message_id FROM processed_alert_emails WHERE source = ? AND message_id IN ({placeholders})",
                (source, *ids),
            ).fetchall()
        already_processed = {row["message_id"] for row in rows}
        return {message_id for message_id in ids if message_id not in already_processed}

    def mark_processed(self, source: str, message_ids: Iterable[str]) -> None:
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO processed_alert_emails (message_id, source, processed_at) VALUES (?, ?, ?)",
                [(message_id, source, now) for message_id in ids],
            )
