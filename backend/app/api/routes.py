from fastapi import APIRouter, Depends, HTTPException

from app.ingestion.scheduler import reschedule
from app.ingestion.services.ingestion_service import IngestionService
from app.models.ingestion_settings import IngestionSettings
from app.models.job import Job, JobCreate
from app.models.preference import KeywordUpdate, Preference, PreferenceCreate
from app.services.errors import DuplicateResourceError
from app.services.ingestion_settings_service import IngestionSettingsService
from app.services.job_service import JobService
from app.services.preference_service import PreferenceService

router = APIRouter()


def get_job_service() -> JobService:
    return JobService()


def get_preference_service() -> PreferenceService:
    return PreferenceService()


def get_ingestion_settings_service() -> IngestionSettingsService:
    return IngestionSettingsService()


def get_ingestion_service() -> IngestionService:
    return IngestionService()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/jobs", response_model=list[Job], tags=["jobs"])
def list_jobs(service: JobService = Depends(get_job_service)) -> list[Job]:
    return service.get_jobs()


@router.post("/jobs", response_model=Job, tags=["jobs"])
def create_job(payload: JobCreate, service: JobService = Depends(get_job_service)) -> Job:
    try:
        return service.add_job(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/preferences", response_model=list[Preference], tags=["preferences"])
def list_preferences(service: PreferenceService = Depends(get_preference_service)) -> list[Preference]:
    return service.get_preferences()


@router.post("/preferences", response_model=Preference, tags=["preferences"])
def create_preference(
    payload: PreferenceCreate, service: PreferenceService = Depends(get_preference_service)
) -> Preference:
    try:
        return service.add_preference(payload)
    except DuplicateResourceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/preferences/{preference_id}", tags=["preferences"])
def delete_preference(preference_id: int, service: PreferenceService = Depends(get_preference_service)) -> dict[str, str]:
    service.remove_preference(preference_id)
    return {"status": "deleted"}


@router.get("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def get_ingestion_settings(service: IngestionSettingsService = Depends(get_ingestion_settings_service)) -> IngestionSettings:
    return service.get_settings()


@router.put("/ingestion/settings", response_model=IngestionSettings, tags=["ingestion"])
def update_ingestion_settings(
    payload: IngestionSettings, service: IngestionSettingsService = Depends(get_ingestion_settings_service)
) -> IngestionSettings:
    updated = service.update_settings(payload)
    reschedule(updated.poll_interval_hours)
    return updated


@router.post("/ingest", tags=["ingestion"])
def ingest_jobs(service: IngestionService = Depends(get_ingestion_service)) -> dict[str, int]:
    return service.run()


@router.post("/ingest/keywords", tags=["ingestion"])
def update_keywords(
    payload: KeywordUpdate, service: PreferenceService = Depends(get_preference_service)
) -> dict[str, list[str]]:
    config = service.replace_keywords(payload.include_keywords, payload.exclude_keywords)
    return {
        "include_keywords": config.include_keywords,
        "exclude_keywords": config.exclude_keywords,
    }
