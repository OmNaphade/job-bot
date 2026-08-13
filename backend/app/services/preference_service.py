from typing import List

from app.ingestion.models import KeywordConfig, KeywordFilter
from app.models.preference import Preference, PreferenceCreate
from app.repositories.preference_repository import PreferenceRepository


class PreferenceService:
    def __init__(self, repository: PreferenceRepository | None = None) -> None:
        self.repository = repository or PreferenceRepository()

    def get_preferences(self, user_id: int) -> List[Preference]:
        return self.repository.list_preferences(user_id)

    def add_preference(self, user_id: int, payload: PreferenceCreate) -> Preference:
        return self.repository.create_preference(user_id, payload)

    def remove_preference(self, user_id: int, preference_id: int) -> None:
        self.repository.delete_preference(user_id, preference_id)

    def get_keyword_config(self, user_id: int) -> KeywordConfig:
        preferences = self.repository.list_preferences(user_id)
        return KeywordConfig(
            include_keywords=[KeywordFilter(p.keyword, p.location) for p in preferences if p.kind == "include"],
            exclude_keywords=[KeywordFilter(p.keyword, p.location) for p in preferences if p.kind == "exclude"],
        )

    def replace_keywords(self, user_id: int, include_keywords: List[str], exclude_keywords: List[str]) -> KeywordConfig:
        include = self.repository.replace_kind(user_id, "include", include_keywords)
        exclude = self.repository.replace_kind(user_id, "exclude", exclude_keywords)
        return KeywordConfig(
            include_keywords=[KeywordFilter(k) for k in include],
            exclude_keywords=[KeywordFilter(k) for k in exclude],
        )
