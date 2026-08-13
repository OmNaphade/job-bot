import dataclasses

import pytest

from app.models.user import LoginRequest, UserCreate
from app.repositories.session_repository import SessionRepository
from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService
from app.services.errors import DuplicateResourceError, InvalidCredentialsError


def test_signup_creates_user_and_returns_token(tmp_db):
    response = AuthService().signup(UserCreate(email="new@example.com", password="password123"))

    assert response.user.email == "new@example.com"
    assert response.token
    assert SessionRepository().get_valid_session(response.token) == response.user.id


def test_signup_raises_on_duplicate_email(tmp_db):
    AuthService().signup(UserCreate(email="dup@example.com", password="password123"))
    with pytest.raises(DuplicateResourceError):
        AuthService().signup(UserCreate(email="dup@example.com", password="password456"))


def test_login_succeeds_with_correct_password(tmp_db):
    AuthService().signup(UserCreate(email="user@example.com", password="password123"))

    response = AuthService().login(LoginRequest(email="user@example.com", password="password123"))

    assert response.user.email == "user@example.com"
    assert response.token


def test_login_raises_on_wrong_password(tmp_db):
    AuthService().signup(UserCreate(email="user@example.com", password="password123"))

    with pytest.raises(InvalidCredentialsError):
        AuthService().login(LoginRequest(email="user@example.com", password="wrong-password"))


def test_login_raises_on_unknown_email(tmp_db):
    with pytest.raises(InvalidCredentialsError):
        AuthService().login(LoginRequest(email="nobody@example.com", password="password123"))


def test_logout_deletes_the_session(tmp_db):
    response = AuthService().signup(UserCreate(email="user@example.com", password="password123"))

    AuthService().logout(response.token)

    assert SessionRepository().get_valid_session(response.token) is None


def test_signup_requires_invite_code_when_configured(tmp_db, monkeypatch):
    configured = dataclasses.replace(auth_service_module.env_settings, signup_invite_code="letmein")
    monkeypatch.setattr(auth_service_module, "env_settings", configured)

    with pytest.raises(InvalidCredentialsError):
        AuthService().signup(UserCreate(email="user@example.com", password="password123"))

    response = AuthService().signup(
        UserCreate(email="user@example.com", password="password123", invite_code="letmein")
    )
    assert response.user.email == "user@example.com"


def test_signup_open_when_invite_code_unconfigured(tmp_db, monkeypatch):
    configured = dataclasses.replace(auth_service_module.env_settings, signup_invite_code=None)
    monkeypatch.setattr(auth_service_module, "env_settings", configured)

    response = AuthService().signup(UserCreate(email="user@example.com", password="password123"))
    assert response.user.email == "user@example.com"
