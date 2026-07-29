import email
import email.message
import imaplib
import logging
from typing import Callable, List, Optional

from app.core.config import settings
from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

ParserFn = Callable[[str], List[JobCandidate]]


class EmailAdapter(BaseAdapter):
    """Reads job postings out of provider alert emails via IMAP.

    Never talks to LinkedIn/Naukri directly -- the user sets up the portal's own
    saved-search email alerts, forwarded to this inbox, and we only parse those.
    """

    def __init__(self, source_name: str, sender: str, parser: ParserFn, enabled: bool = False) -> None:
        self.source_name = source_name
        self.sender = sender
        self.parser = parser
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        if not settings.alert_email_address or not settings.alert_email_app_password:
            logger.warning(
                "Email source '%s' is enabled but ALERT_EMAIL_ADDRESS/ALERT_EMAIL_APP_PASSWORD are unset; skipping.",
                self.source_name,
            )
            return []

        try:
            connection = imaplib.IMAP4_SSL(settings.alert_email_imap_host, settings.alert_email_imap_port)
        except Exception:
            logger.exception("Failed to connect to IMAP host for source '%s'", self.source_name)
            return []

        candidates: List[JobCandidate] = []
        try:
            connection.login(settings.alert_email_address, settings.alert_email_app_password)
            connection.select("INBOX")
            status, message_numbers = connection.search(None, "UNSEEN", "FROM", f'"{self.sender}"')
            if status != "OK":
                logger.warning("IMAP search failed for source '%s': %s", self.source_name, status)
                return []

            for message_number in message_numbers[0].split():
                candidates.extend(self._process_message(connection, message_number))
        except Exception:
            logger.exception("Failed while reading alert emails for source '%s'", self.source_name)
        finally:
            try:
                connection.logout()
            except Exception:
                pass

        return candidates

    def _process_message(self, connection: imaplib.IMAP4_SSL, message_number: bytes) -> List[JobCandidate]:
        status, data = connection.fetch(message_number, "(BODY.PEEK[])")
        if status != "OK" or not data or not isinstance(data[0], tuple):
            return []

        message = email.message_from_bytes(data[0][1])
        html = self._extract_html(message)
        if not html:
            return []

        try:
            parsed = self.parser(html)
        except Exception:
            logger.exception("Failed to parse alert email body for source '%s'", self.source_name)
            return []

        connection.store(message_number, "+FLAGS", "\\Seen")
        return parsed

    def _extract_html(self, message: email.message.Message) -> Optional[str]:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/html":
                    return self._decode_payload(part)
            return None

        if message.get_content_type() == "text/html":
            return self._decode_payload(message)
        return None

    def _decode_payload(self, part: email.message.Message) -> Optional[str]:
        payload = part.get_payload(decode=True)
        if not payload:
            return None
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
