import pytest

from app.db import database


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    database.init_db()
    return db_path


@pytest.fixture
def test_user(tmp_db):
    """A real persisted user, for tests that need a user_id to scope data
    against without exercising the full signup flow themselves."""
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository

    return UserRepository().create("test@example.com", hash_password("password123"))


@pytest.fixture
def auth_headers(test_user):
    """Authorization header for `test_user`, for route tests via TestClient."""
    from app.repositories.session_repository import SessionRepository

    token = SessionRepository().create(test_user.id)
    return {"Authorization": f"Bearer {token}"}
