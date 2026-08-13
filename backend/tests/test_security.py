import pytest
from fastapi import HTTPException

from app.core.security import get_current_user, hash_password, verify_password
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository


def test_hash_password_round_trips():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_hash_password_salts_differently_each_time():
    assert hash_password("same-password") != hash_password("same-password")


def test_verify_password_returns_false_for_malformed_hash():
    assert verify_password("anything", "not-a-real-bcrypt-hash") is False


def test_get_current_user_rejects_missing_header(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_non_bearer_header(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user("not-a-bearer-token")
    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_unknown_token(tmp_db):
    with pytest.raises(HTTPException) as exc_info:
        get_current_user("Bearer does-not-exist")
    assert exc_info.value.status_code == 401


def test_get_current_user_resolves_valid_session(tmp_db):
    record = UserRepository().create("user@example.com", hash_password("password123"))
    token = SessionRepository().create(record.id)

    user = get_current_user(f"Bearer {token}")

    assert user.id == record.id
    assert user.email == "user@example.com"
