from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models.match import JobMatch
from app.models.user import User
from app.services.matching_service import MatchingService

# No auth dependency declared here -- included into routes.py's `protected`
# sub-router, same pattern as resume_routes.py.
router = APIRouter()


def get_matching_service() -> MatchingService:
    return MatchingService()


@router.get("/matches", response_model=list[JobMatch], tags=["matching"])
def list_matches(
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    service: MatchingService = Depends(get_matching_service),
) -> list[JobMatch]:
    return service.get_matches(current_user.id, limit, offset)
