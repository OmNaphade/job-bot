from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db import database
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository


def _make_user(email: str = "user@example.com"):
    return UserRepository().create(email, hash_password("password123"))


def test_create_returns_a_token_that_resolves_to_the_user(tmp_db):
    user = _make_user()
    token = SessionRepository().create(user.id)

    assert SessionRepository().get_valid_session(token) == user.id


def test_get_valid_session_returns_none_for_unknown_token(tmp_db):
    assert SessionRepository().get_valid_session("does-not-exist") is None


def test_get_valid_session_returns_none_for_expired_token(tmp_db):
    user = _make_user()
    token = SessionRepository().create(user.id)
    # Force it into the past directly via SQL -- Settings is a frozen
    # dataclass, so there's no field to monkeypatch to shrink the TTL instead.
    with database.db_session() as connection:
        connection.execute(
            "UPDATE sessions SET expires_at = %s WHERE token = %s",
            (datetime.now(timezone.utc) - timedelta(days=1), token),
        )

    assert SessionRepository().get_valid_session(token) is None


def test_delete_invalidates_the_session(tmp_db):
    user = _make_user()
    token = SessionRepository().create(user.id)

    SessionRepository().delete(token)

    assert SessionRepository().get_valid_session(token) is None


def test_delete_unknown_token_does_not_raise(tmp_db):
    SessionRepository().delete("does-not-exist")
