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

    Never talks to LinkedIn/Naukri/Foundit directly -- the user sets up the
    portal's own saved-search/job-match email alerts, and we only parse those.

    Searches every mailbox in `mailboxes` (default just INBOX) for unread mail,
    optionally filtered by `sender` (a Gmail IMAP FROM search is a substring
    match, not exact). This is what lets it check both INBOX and a Gmail label
    folder the user has a filter routing alerts into -- Gmail exposes labels as
    IMAP mailboxes. A message that's both in INBOX and a label (label applied
    without "skip the inbox") is naturally only processed once: Gmail shares
    the \\Seen flag across all views of the same message, so marking it seen
    while processing one mailbox makes it drop out of the UNSEEN search in the
    other. A mailbox that doesn't exist yet (e.g. the label hasn't been
    created) is skipped with a warning, not a hard failure.
    """

    def __init__(
        self,
        source_name: str,
        parser: ParserFn,
        sender: Optional[str] = None,
        mailboxes: Optional[List[str]] = None,
        enabled: bool = False,
    ) -> None:
        self.source_name = source_name
        self.sender = sender
        self.parser = parser
        self.mailboxes = mailboxes or ["INBOX"]
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
            for mailbox in self.mailboxes:
                candidates.extend(self._fetch_from_mailbox(connection, mailbox))
        except Exception:
            logger.exception("Failed while reading alert emails for source '%s'", self.source_name)
        finally:
            try:
                connection.logout()
            except Exception:
                pass

        return candidates

    def _fetch_from_mailbox(self, connection: imaplib.IMAP4_SSL, mailbox: str) -> List[JobCandidate]:
        status, _ = connection.select(f'"{mailbox}"')
        if status != "OK":
            logger.warning(
                "Mailbox '%s' not found/selectable for source '%s' (does the Gmail label exist yet?); skipping.",
                mailbox,
                self.source_name,
            )
            return []

        search_criteria = ["UNSEEN"]
        if self.sender:
            search_criteria += ["FROM", f'"{self.sender}"']
        status, message_numbers = connection.search(None, *search_criteria)
        if status != "OK":
            logger.warning("IMAP search failed for source '%s' in mailbox '%s': %s", self.source_name, mailbox, status)
            return []

        candidates: List[JobCandidate] = []
        for message_number in message_numbers[0].split():
            candidates.extend(self._process_message(connection, message_number))
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
