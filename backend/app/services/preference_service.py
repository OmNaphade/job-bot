from typing import List

from app.ingestion.models import KeywordConfig
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
        return KeywordConfig(
            include_keywords=self.repository.list_keywords_by_kind("include"),
            exclude_keywords=self.repository.list_keywords_by_kind("exclude"),
        )

    def replace_keywords(self, include_keywords: List[str], exclude_keywords: List[str]) -> KeywordConfig:
        include = self.repository.replace_kind("include", include_keywords)
        exclude = self.repository.replace_kind("exclude", exclude_keywords)
        return KeywordConfig(include_keywords=include, exclude_keywords=exclude)
