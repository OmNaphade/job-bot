from typing import List

from app.models.match import JobMatch
from app.repositories.matching_repository import MatchingRepository
from app.repositories.resume_repository import ResumeRepository


class MatchingService:
    def __init__(
        self, matching_repository: MatchingRepository | None = None, resume_repository: ResumeRepository | None = None
    ) -> None:
        self.matching_repository = matching_repository or MatchingRepository()
        self.resume_repository = resume_repository or ResumeRepository()

    def get_matches(self, user_id: int, limit: int = 20, offset: int = 0) -> List[JobMatch]:
        # No resume uploaded yet -> empty list, a clear "upload a resume to
        # see matches" state in the UI, not an error.
        embedding = self.resume_repository.get_embedding(user_id)
        if embedding is None:
            return []
        return self.matching_repository.find_matches(user_id, embedding, limit, offset)
