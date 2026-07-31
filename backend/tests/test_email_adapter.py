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


class _FakeImap:
    """Mimics just enough of imaplib.IMAP4_SSL for EmailAdapter's fetch() flow.

    `mailbox_contents` maps mailbox name -> list of message numbers that exist
    there (as bytes, IMAP-style). Mailboxes not present in the dict are treated
    as non-existent (select() fails), simulating a Gmail label that hasn't been
    created yet.
    """

    def __init__(self, mailbox_contents: dict[str, list[bytes]]):
        self.mailbox_contents = mailbox_contents
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

    def fetch(self, message_number, _spec):
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
    )
    candidates = adapter.fetch()

    assert fake.selected_mailboxes_in_order == ["INBOX", "linkedin-alerts"]
    assert len(candidates) == 2  # one per mailbox, from the fake parser
    assert all(criteria[0] == "UNSEEN" and "FROM" in criteria for criteria in fake.search_calls)


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
    )
    candidates = adapter.fetch()

    assert len(candidates) == 1  # only INBOX contributed
    assert fake.search_calls == [("UNSEEN",)]  # no FROM criterion when sender is None


def test_fetch_returns_empty_when_credentials_unset(monkeypatch):
    monkeypatch.setattr("app.ingestion.adapters.email_adapter.settings", _UNCONFIGURED_SETTINGS)

    adapter = EmailAdapter("test_source", parser=_fake_parser, enabled=True)
    assert adapter.fetch() == []
