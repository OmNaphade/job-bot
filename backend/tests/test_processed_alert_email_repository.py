from app.repositories.processed_alert_email_repository import ProcessedAlertEmailRepository


def test_filter_new_returns_all_ids_when_none_processed_yet(tmp_db):
    repo = ProcessedAlertEmailRepository()

    assert repo.filter_new("linkedin_alerts", ["<a@example.com>", "<b@example.com>"]) == {
        "<a@example.com>",
        "<b@example.com>",
    }


def test_filter_new_excludes_ids_already_marked_processed(tmp_db):
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed("linkedin_alerts", ["<a@example.com>"])

    assert repo.filter_new("linkedin_alerts", ["<a@example.com>", "<b@example.com>"]) == {"<b@example.com>"}


def test_filter_new_is_scoped_per_source(tmp_db):
    # The same alert-digest could plausibly be processed under a different source
    # name in a differently-configured adapter -- processed state shouldn't leak
    # across sources.
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed("linkedin_alerts", ["<a@example.com>"])

    assert repo.filter_new("naukri_alerts", ["<a@example.com>"]) == {"<a@example.com>"}


def test_mark_processed_is_idempotent(tmp_db):
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed("linkedin_alerts", ["<a@example.com>"])
    repo.mark_processed("linkedin_alerts", ["<a@example.com>"])  # should not raise

    assert repo.filter_new("linkedin_alerts", ["<a@example.com>"]) == set()


def test_filter_new_handles_empty_input():
    repo = ProcessedAlertEmailRepository()
    assert repo.filter_new("linkedin_alerts", []) == set()
