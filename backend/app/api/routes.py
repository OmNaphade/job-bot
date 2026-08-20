from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api import matching_routes, resume_routes
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import extract_bearer_token, get_current_user
from app.ingestion.services.ingestion_service import IngestionService
from app.models.ingestion_run import IngestionRun
from app.models.ingestion_settings import IngestionSettings
from app.models.job import Job, JobCreate
from app.models.notification_settings import NotificationSettings
from app.models.preference import KeywordUpdate, Preference, PreferenceCreate
from app.models.user import AuthResponse, LoginRequest, User, UserCreate
from app.services.auth_service import AuthService
from app.services.errors import DuplicateResourceError, InvalidCredentialsError
from app.services.ingestion_run_service import IngestionRunService
from app.services.ingestion_settings_service import IngestionSettingsService
from app.services.job_service import JobService
from app.services.notification_settings_service import NotificationSettingsService
from app.services.preference_service import PreferenceService

router = APIRouter()
# Everything except /health, /auth/signup, and /auth/login requires a valid
# session token (Authorization: Bearer <token>), resolved by get_current_user
# in app/core/security.py -- see that module for the auth design.
protected = APIRouter(dependencies=[Depends(get_current_user)])


def get_job_service() -> JobService:
    return JobService()


def get_preference_service() -> PreferenceService:
    return PreferenceService()


def get_ingestion_settings_service() -> IngestionSettingsService:
    return IngestionSettingsService()


def get_notification_settings_service() -> NotificationSettingsService:
    return NotificationSettingsService()


def get_ingestion_service() -> IngestionService:
    return IngestionService()


def get_ingestion_run_service() -> IngestionRunService:
    return IngestionRunService()


def get_auth_service() -> AuthService:
    return AuthService()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/signup", response_model=AuthResponse, tags=["auth"])
@limiter.limit(settings.signup_rate_limit)
def signup(
    request: Request, payload: UserCreate, service: AuthService = Depends(get_auth_service)
) -> AuthResponse:
    try:
        return service.signup(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
@limiter.limit(settings.login_rate_limit)
def login(
    request: Request, payload: LoginRequest, service: AuthService = Depends(get_auth_service)
) -> AuthResponse:
    try:
        return service.login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@protected.post("/auth/logout", tags=["auth"])
def logout(authorization: str | None = Header(default=None), service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    service.logout(extract_bearer_token(authorization))
    return {"status": "logged out"}


@protected.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(current_user: User = Depends(get_current_user), service: JobService = Depends(get_job_service)) -> list[Job]:
    return service.get_jobs(current_user.id)


@protected.post("/jobs", response_model=Job, tags=["jobs"])
def create_job(
    payload: JobCreate, current_user: User = Depends(get_current_user), service: JobService = Depends(get_job_service)
) -> Job:
    try:
        return service.add_job(current_user.id, payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@protected.get("/preferences", response_model=list[Preference], tags=["preferences"])
def list_preferences(
    current_user: User = Depends(get_current_user), service: PreferenceService = Depends(get_preference_service)
) -> list[Preference]:
    return service.get_preferences(current_user.id)


@protected.post("/preferences", response_model=Preference, tags=["preferences"])
def create_preference(
    payload: PreferenceCreate,
    current_user: User = Depends(get_current_user),
    service: PreferenceService = Depends(get_preference_service),
) -> Preference:
    try:
        return service.add_preference(current_user.id, payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@protected.delete("/preferences/{preference_id}", tags=["preferences"])
def delete_preference(
    preference_id: int,
    current_user: User = Depends(get_current_user),
    service: PreferenceService = Depends(get_preference_service),
) -> dict[str, str]:
    service.remove_preference(current_user.id, preference_id)
    return {"status": "deleted"}


@protected.get("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def get_ingestion_settings(
    current_user: User = Depends(get_current_user),
    service: IngestionSettingsService = Depends(get_ingestion_settings_service),
) -> IngestionSettings:
    return service.get_settings(current_user.id)


@protected.put("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def update_ingestion_settings(
    payload: IngestionSettings,
    current_user: User = Depends(get_current_user),
    service: IngestionSettingsService = Depends(get_ingestion_settings_service),
) -> IngestionSettings:
    return service.update_settings(current_user.id, payload)


@protected.get("/notification-settings", response_model=NotificationSettings, tags=["notifications"])
def get_notification_settings(
    current_user: User = Depends(get_current_user),
    service: NotificationSettingsService = Depends(get_notification_settings_service),
) -> NotificationSettings:
    return service.get_settings(current_user.id)


@protected.put("/notification-settings", response_model=NotificationSettings, tags=["notifications"])
def update_notification_settings(
    payload: NotificationSettings,
    current_user: User = Depends(get_current_user),
    service: NotificationSettingsService = Depends(get_notification_settings_service),
) -> NotificationSettings:
    return service.update_settings(current_user.id, payload)


@protected.post("/ingest", tags=["ingestion"])
def ingest_jobs(
    current_user: User = Depends(get_current_user), service: IngestionService = Depends(get_ingestion_service)
) -> dict[str, Any]:
    return service.run_for_user(current_user.id)


@protected.get("/ingestion/runs", response_model=list[IngestionRun], tags=["ingestion"])
def list_ingestion_runs(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    service: IngestionRunService = Depends(get_ingestion_run_service),
) -> list[IngestionRun]:
    return service.get_recent_runs(current_user.id, limit)


@protected.post("/ingest/keywords", tags=["ingestion"])
def update_keywords(
    payload: KeywordUpdate,
    current_user: User = Depends(get_current_user),
    service: PreferenceService = Depends(get_preference_service),
) -> dict[str, list[str]]:
    config = service.replace_keywords(current_user.id, payload.include_keywords, payload.exclude_keywords)
    return {
        "include_keywords": [f.keyword for f in config.include_keywords],
        "exclude_keywords": [f.keyword for f in config.exclude_keywords],
    }


protected.include_router(resume_routes.router)
protected.include_router(matching_routes.router)

router.include_router(protected)
