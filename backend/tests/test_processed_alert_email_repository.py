from app.core.security import hash_password
from app.repositories.processed_alert_email_repository import ProcessedAlertEmailRepository
from app.repositories.user_repository import UserRepository


def test_filter_new_returns_all_ids_when_none_processed_yet(test_user):
    repo = ProcessedAlertEmailRepository()

    assert repo.filter_new(test_user.id, "linkedin_alerts", ["<a@example.com>", "<b@example.com>"]) == {
        "<a@example.com>",
        "<b@example.com>",
    }


def test_filter_new_excludes_ids_already_marked_processed(test_user):
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed(test_user.id, "linkedin_alerts", ["<a@example.com>"])

    assert repo.filter_new(test_user.id, "linkedin_alerts", ["<a@example.com>", "<b@example.com>"]) == {"<b@example.com>"}


def test_filter_new_is_scoped_per_source(test_user):
    # The same alert-digest could plausibly be processed under a different source
    # name in a differently-configured adapter -- processed state shouldn't leak
    # across sources.
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed(test_user.id, "linkedin_alerts", ["<a@example.com>"])

    assert repo.filter_new(test_user.id, "naukri_alerts", ["<a@example.com>"]) == {"<a@example.com>"}


def test_filter_new_is_scoped_per_user(test_user, tmp_db):
    # Two users can both enable the same alert channel against the same shared
    # mailbox -- one user's pass marking a message processed must not hide it
    # from another user's pass.
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed(test_user.id, "linkedin_alerts", ["<a@example.com>"])

    assert repo.filter_new(other_user.id, "linkedin_alerts", ["<a@example.com>"]) == {"<a@example.com>"}


def test_mark_processed_is_idempotent(test_user):
    repo = ProcessedAlertEmailRepository()
    repo.mark_processed(test_user.id, "linkedin_alerts", ["<a@example.com>"])
    repo.mark_processed(test_user.id, "linkedin_alerts", ["<a@example.com>"])  # should not raise

    assert repo.filter_new(test_user.id, "linkedin_alerts", ["<a@example.com>"]) == set()


def test_filter_new_handles_empty_input(test_user):
    repo = ProcessedAlertEmailRepository()
    assert repo.filter_new(test_user.id, "linkedin_alerts", []) == set()
