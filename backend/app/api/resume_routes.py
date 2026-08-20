from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.security import get_current_user
from app.models.resume import ResumeProfile
from app.models.user import User
from app.services.errors import AIExtractionError, ResumeUploadLimitExceeded
from app.services.resume_service import ResumeService

# No auth dependency declared here -- this router is included into routes.py's
# `protected` sub-router (which already carries Depends(get_current_user)),
# same pattern as every other feature area. Kept in its own module/router
# object purely to keep routes.py from growing without bound as new feature
# areas (this one, then matching) get added.
router = APIRouter()

MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5MB -- resumes are text documents, not media.


def get_resume_service() -> ResumeService:
    return ResumeService()


@router.post("/resume", response_model=ResumeProfile, tags=["resume"])
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
) -> ResumeProfile:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > MAX_RESUME_BYTES:
        raise HTTPException(status_code=413, detail="Resume file is too large (max 5MB)")

    try:
        return service.upload(current_user.id, pdf_bytes, file.filename)
    except ResumeUploadLimitExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AIExtractionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/resume", response_model=Optional[ResumeProfile], tags=["resume"])
def get_resume(
    current_user: User = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
) -> Optional[ResumeProfile]:
    return service.get_profile(current_user.id)


@router.delete("/resume", tags=["resume"])
def delete_resume(
    current_user: User = Depends(get_current_user),
    service: ResumeService = Depends(get_resume_service),
) -> dict[str, str]:
    service.delete(current_user.id)
    return {"status": "deleted"}
