import email.message
from types import SimpleNamespace

from app.ingestion.adapters.email_adapter import EmailAdapter
from app.ingestion.models import JobCandidate

_CONFIGURED_SETTINGS = SimpleNamespace(
    alert_email_address="bot@example.com",
    alert_email_app_password="app-password",
    alert_email_imap_host="imap.gmail.com",
    alert_email_imap_port=993,
)
_UNCONFIGURED_SETTINGS = SimpleNamespace(
    alert_email_address=None,
    alert_email_app_password=None,
    alert_email_imap_host="imap.gmail.com",
    alert_email_imap_port=993,
)


def _build_html_email(html: str) -> bytes:
    message = email.message.EmailMessage()
    message.set_content(html, subtype="html")
    return message.as_bytes()


def _fake_parser(html: str):
    return [JobCandidate(title="Parsed Job", company="Acme", location="Remote", link="https://example.com/1", source="test")]


class _FakeProcessedRepo:
    """In-memory stand-in for ProcessedAlertEmailRepository."""

    def __init__(self, already_processed=None):
        self.already_processed: set[str] = set(already_processed or [])
        self.marked: list[tuple[str, str]] = []

    def filter_new(self, source, message_ids):
        return {message_id for message_id in message_ids if message_id not in self.already_processed}

    def mark_processed(self, source, message_ids):
        for message_id in message_ids:
            self.marked.append((source, message_id))
            self.already_processed.add(message_id)


class _FakeImap:
    """Mimics just enough of imaplib.IMAP4_SSL for EmailAdapter's fetch() flow.

    `mailbox_contents` maps mailbox name -> list of message numbers that exist
    there (as bytes, IMAP-style). Mailboxes not present in the dict are treated
    as non-existent (select() fails), simulating a Gmail label that hasn't been
    created yet. Each message's Message-ID defaults to `<{number}@example.com>`
    unless overridden via `message_ids`.
    """

    def __init__(self, mailbox_contents: dict[str, list[bytes]], message_ids: dict[bytes, str] | None = None):
        self.mailbox_contents = mailbox_contents
        self.message_ids = message_ids or {}
        self.selected_mailbox = None
        self.selected_mailboxes_in_order: list[str] = []
        self.search_calls: list[tuple] = []
        self.stored_seen: list[bytes] = []

    def login(self, *_args, **_kwargs):
        return "OK", []

    def select(self, mailbox):
        name = mailbox.strip('"')
        self.selected_mailboxes_in_order.append(name)
        if name not in self.mailbox_contents:
            return "NO", [b"mailbox does not exist"]
        self.selected_mailbox = name
        return "OK", []

    def search(self, _charset, *criteria):
        self.search_calls.append(criteria)
        numbers = self.mailbox_contents.get(self.selected_mailbox, [])
        return "OK", [b" ".join(numbers)]

    def fetch(self, message_number, spec):
        if "MESSAGE-ID" in spec:
            message_id = self.message_ids.get(message_number, f"<{message_number.decode()}@example.com>")
            header = f"Message-ID: {message_id}\r\n\r\n".encode()
            return "OK", [(b"1 (BODY[HEADER.FIELDS (MESSAGE-ID)])", header)]
        html_email = _build_html_email(f"<a href='https://example.com/{message_number.decode()}'>Job</a>")
        return "OK", [(b"1 (BODY[])", html_email)]

    def store(self, message_number, _flags_op, _flags):
        self.stored_seen.append(message_number)
        return "OK", []

    def logout(self):
        return "OK", []


def test_fetch_returns_empty_when_disabled():
    adapter = EmailAdapter("test_source", parser=_fake_parser, enabled=False)
    assert adapter.fetch() == []


def test_fetch_searches_inbox_and_label_mailbox(monkeypatch):
    fake = _FakeImap({"INBOX": [b"1"], "linkedin-alerts": [b"2"]})
    monkeypatch.setattr(
        "app.ingestion.adapters.email_adapter.imaplib.IMAP4_SSL", lambda *a, **kw: fake
    )
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _CONFIGURED_SETTINGS)

    adapter = EmailAdapter(
        "linkedin_alerts",
        parser=_fake_parser,
        sender="jobalerts-noreply@linkedin.com",
        mailboxes=["INBOX", "linkedin-alerts"],
        enabled=True,
        processed_repo=_FakeProcessedRepo(),
    )
    candidates = adapter.fetch()

    assert fake.selected_mailboxes_in_order == ["INBOX", "linkedin-alerts"]
    assert len(candidates) == 2  # one per mailbox, from the fake parser
    assert all(criteria[0] == "SINCE" and "FROM" in criteria for criteria in fake.search_calls)


def test_fetch_skips_mailbox_that_does_not_exist(monkeypatch):
    fake = _FakeImap({"INBOX": [b"1"]})  # "foundit-alerts" label not created yet
    monkeypatch.setattr(
        "app.ingestion.adapters.email_adapter.imaplib.IMAP4_SSL", lambda *a, **kw: fake
    )
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _CONFIGURED_SETTINGS)

    adapter = EmailAdapter(
        "foundit_alerts",
        parser=_fake_parser,
        sender=None,
        mailboxes=["INBOX", "foundit-alerts"],
        enabled=True,
        processed_repo=_FakeProcessedRepo(),
    )
    candidates = adapter.fetch()

    assert len(candidates) == 1  # only INBOX contributed
    assert fake.search_calls == [("SINCE", fake.search_calls[0][1])]  # no FROM criterion when sender is None


def test_fetch_returns_empty_when_credentials_unset(monkeypatch):
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _UNCONFIGURED_SETTINGS)

    adapter = EmailAdapter("test_source", parser=_fake_parser, enabled=True)
    assert adapter.fetch() == []


def test_fetch_ignores_message_already_marked_processed(monkeypatch):
    """Regression test: a Gmail filter that marks alert emails as read on arrival
    (or the user reading their own mail) used to make an IMAP UNSEEN search
    silently skip real, matching alerts forever, contributing zero candidates.
    Processed-state now lives in our own DB, keyed by Message-ID, not the
    mailbox's \\Seen flag -- so it isn't affected by anything else touching the
    mailbox. This test simulates a message that's already been processed
    (whether by a prior run or found already-seen) and checks it's skipped.
    """
    fake = _FakeImap({"INBOX": [b"1"]}, message_ids={b"1": "<already-seen@example.com>"})
    monkeypatch.setattr(
        "app.ingestion.adapters.email_adapter.imaplib.IMAP4_SSL", lambda *a, **kw: fake
    )
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _CONFIGURED_SETTINGS)
    repo = _FakeProcessedRepo(already_processed={"<already-seen@example.com>"})

    adapter = EmailAdapter("test_source", parser=_fake_parser, mailboxes=["INBOX"], enabled=True, processed_repo=repo)
    candidates = adapter.fetch()

    assert candidates == []


def test_fetch_marks_new_message_as_processed_after_parsing(monkeypatch):
    fake = _FakeImap({"INBOX": [b"1"]}, message_ids={b"1": "<new-message@example.com>"})
    monkeypatch.setattr(
        "app.ingestion.adapters.email_adapter.imaplib.IMAP4_SSL", lambda *a, **kw: fake
    )
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _CONFIGURED_SETTINGS)
    repo = _FakeProcessedRepo()

    adapter = EmailAdapter("test_source", parser=_fake_parser, mailboxes=["INBOX"], enabled=True, processed_repo=repo)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    assert repo.marked == [("test_source", "<new-message@example.com>")]
