from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.rate_limit import limiter


def _full_client() -> TestClient:
    """Mirrors main.py's exact rate-limit wiring (app.state.limiter +
    exception handler + middleware) -- test_routes.py's bare
    `FastAPI(); app.include_router(router)` deliberately skips all of that,
    so it can't be used to verify a 429 actually comes back correctly (only
    that the happy path still works without it getting in the way)."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)
    return TestClient(app)


def _signups_allowed_per_window() -> int:
    # @limiter.limit(settings.signup_rate_limit) reads this once at import
    # time (decorators apply at module load, not per-request) -- so tests
    # can't shrink the limit via monkeypatch, only read the real configured
    # value and drive exactly that many + 1 requests.
    return int(settings.signup_rate_limit.split("/")[0])


def test_signup_succeeds_up_to_the_configured_limit(tmp_db):
    client = _full_client()
    allowed = _signups_allowed_per_window()

    for i in range(allowed):
        response = client.post("/auth/signup", json={"email": f"user{i}@example.com", "password": "password123"})
        assert response.status_code == 200, response.text


def test_signup_returns_429_once_the_limit_is_exceeded(tmp_db):
    client = _full_client()
    allowed = _signups_allowed_per_window()

    for i in range(allowed):
        client.post("/auth/signup", json={"email": f"user{i}@example.com", "password": "password123"})

    response = client.post("/auth/signup", json={"email": "one-too-many@example.com", "password": "password123"})

    assert response.status_code == 429


def test_login_rate_limit_is_independent_of_signup(tmp_db):
    # Different endpoints get independent limit buckets (keyed by endpoint +
    # IP) -- exhausting signup's limit must not affect login.
    client = _full_client()
    client.post("/auth/signup", json={"email": "user@example.com", "password": "password123"})
    for i in range(_signups_allowed_per_window()):
        client.post("/auth/signup", json={"email": f"filler{i}@example.com", "password": "password123"})

    response = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})

    assert response.status_code == 200
