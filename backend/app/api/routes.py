from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_api_key
from app.ingestion.scheduler import reschedule
from app.ingestion.services.ingestion_service import IngestionService
from app.models.ingestion_run import IngestionRun
from app.models.ingestion_settings import IngestionSettings
from app.models.job import Job, JobCreate
from app.models.preference import KeywordUpdate, Preference, PreferenceCreate
from app.services.errors import DuplicateResourceError
from app.services.ingestion_run_service import IngestionRunService
from app.services.ingestion_settings_service import IngestionSettingsService
from app.services.job_service import JobService
from app.services.preference_service import PreferenceService

router = APIRouter()
# Everything except /health requires X-API-Key when API_KEY is configured
# (see app/core/security.py) -- /health stays open so connectivity/liveness
# checks work before a client has a key configured.
protected = APIRouter(dependencies=[Depends(require_api_key)])


def get_job_service() -> JobService:
    return JobService()


def get_preference_service() -> PreferenceService:
    return PreferenceService()


def get_ingestion_settings_service() -> IngestionSettingsService:
    return IngestionSettingsService()


def get_ingestion_service() -> IngestionService:
    return IngestionService()


def get_ingestion_run_service() -> IngestionRunService:
    return IngestionRunService()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@protected.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(service: JobService = Depends(get_job_service)) -> list[Job]:
    return service.get_jobs()


@protected.post("/jobs", response_model=Job, tags=["jobs"])
def create_job(payload: JobCreate, service: JobService = Depends(get_job_service)) -> Job:
    try:
        return service.add_job(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@protected.get("/preferences", response_model=list[Preference], tags=["preferences"])
def list_preferences(service: PreferenceService = Depends(get_preference_service)) -> list[Preference]:
    return service.get_preferences()


@protected.post("/preferences", response_model=Preference, tags=["preferences"])
def create_preference(
    payload: PreferenceCreate, service: PreferenceService = Depends(get_preference_service)
) -> Preference:
    try:
        return service.add_preference(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@protected.delete("/preferences/{preference_id}", tags=["preferences"])
def delete_preference(preference_id: int, service: PreferenceService = Depends(get_preference_service)) -> dict[str, str]:
    service.remove_preference(preference_id)
    return {"status": "deleted"}


@protected.get("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def get_ingestion_settings(service: IngestionSettingsService = Depends(get_ingestion_settings_service)) -> IngestionSettings:
    return service.get_settings()


@protected.put("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def update_ingestion_settings(
    payload: IngestionSettings, service: IngestionSettingsService = Depends(get_ingestion_settings_service)
) -> IngestionSettings:
    updated = service.update_settings(payload)
    reschedule(updated.poll_interval_hours)
    return updated


@protected.post("/ingest", tags=["ingestion"])
def ingest_jobs(service: IngestionService = Depends(get_ingestion_service)) -> dict[str, Any]:
    return service.run()


@protected.get("/ingestion/runs", response_model=list[IngestionRun], tags=["ingestion"])
def list_ingestion_runs(
    limit: int = 20, service: IngestionRunService = Depends(get_ingestion_run_service)
) -> list[IngestionRun]:
    return service.get_recent_runs(limit)


@protected.post("/ingest/keywords", tags=["ingestion"])
def update_keywords(
    payload: KeywordUpdate, service: PreferenceService = Depends(get_preference_service)
) -> dict[str, list[str]]:
    config = service.replace_keywords(payload.include_keywords, payload.exclude_keywords)
    return {
        "include_keywords": [f.keyword for f in config.include_keywords],
        "exclude_keywords": [f.keyword for f in config.exclude_keywords],
    }


router.include_router(protected)
