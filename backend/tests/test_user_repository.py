import pytest

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.services.errors import DuplicateResourceError


def test_create_and_get_by_email(tmp_db):
    record = UserRepository().create("user@example.com", hash_password("password123"))

    fetched = UserRepository().get_by_email("user@example.com")
    assert fetched.id == record.id
    assert fetched.password_hash == record.password_hash


def test_create_raises_on_duplicate_email(tmp_db):
    UserRepository().create("dup@example.com", hash_password("password123"))
    with pytest.raises(DuplicateResourceError):
        UserRepository().create("dup@example.com", hash_password("password456"))


def test_get_by_email_returns_none_when_not_found(tmp_db):
    assert UserRepository().get_by_email("nobody@example.com") is None


def test_get_by_id_returns_public_user_without_password_hash(tmp_db):
    record = UserRepository().create("user2@example.com", hash_password("password123"))

    user = UserRepository().get_by_id(record.id)

    assert user.id == record.id
    assert user.email == "user2@example.com"
    assert not hasattr(user, "password_hash")


def test_get_by_id_returns_none_when_not_found(tmp_db):
    assert UserRepository().get_by_id(999999) is None


def test_list_all_ids_returns_every_user(tmp_db):
    a = UserRepository().create("a@example.com", hash_password("password123"))
    b = UserRepository().create("b@example.com", hash_password("password123"))

    assert UserRepository().list_all_ids() == [a.id, b.id]
