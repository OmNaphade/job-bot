from typing import List

from app.ingestion.models import KeywordConfig, KeywordFilter
from app.models.preference import Preference, PreferenceCreate
from app.repositories.preference_repository import PreferenceRepository


class PreferenceService:
    def __init__(self, repository: PreferenceRepository | None = None) -> None:
        self.repository = repository or PreferenceRepository()

    def get_preferences(self) -> List[Preference]:
        return self.repository.list_preferences()

    def add_preference(self, payload: PreferenceCreate) -> Preference:
        return self.repository.create_preference(payload)

    def remove_preference(self, preference_id: int) -> None:
        self.repository.delete_preference(preference_id)

    def get_keyword_config(self) -> KeywordConfig:
        preferences = self.repository.list_preferences()
        return KeywordConfig(
            include_keywords=[KeywordFilter(p.keyword, p.location) for p in preferences if p.kind == "include"],
            exclude_keywords=[KeywordFilter(p.keyword, p.location) for p in preferences if p.kind == "exclude"],
        )

    def replace_keywords(self, include_keywords: List[str], exclude_keywords: List[str]) -> KeywordConfig:
        include = self.repository.replace_kind("include", include_keywords)
        exclude = self.repository.replace_kind("exclude", exclude_keywords)
        return KeywordConfig(
            include_keywords=[KeywordFilter(k) for k in include],
            exclude_keywords=[KeywordFilter(k) for k in exclude],
        )
