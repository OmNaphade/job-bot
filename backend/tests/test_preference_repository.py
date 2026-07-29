import pytest

from app.models.preference import PreferenceCreate
from app.repositories.preference_repository import PreferenceRepository
from app.services.errors import DuplicateResourceError


def test_create_preference_and_list_by_kind(tmp_db):
    repo = PreferenceRepository()
    repo.create_preference(PreferenceCreate(keyword="backend", kind="include"))
    repo.create_preference(PreferenceCreate(keyword="senior", kind="exclude"))

    assert repo.list_keywords_by_kind("include") == ["backend"]
    assert repo.list_keywords_by_kind("exclude") == ["senior"]


def test_create_preference_raises_on_duplicate_keyword_and_kind(tmp_db):
    repo = PreferenceRepository()
    repo.create_preference(PreferenceCreate(keyword="backend", kind="include"))
    with pytest.raises(DuplicateResourceError):
        repo.create_preference(PreferenceCreate(keyword="backend", kind="include"))


def test_same_keyword_allowed_across_different_kinds(tmp_db):
    repo = PreferenceRepository()
    repo.create_preference(PreferenceCreate(keyword="lead", kind="include"))
    repo.create_preference(PreferenceCreate(keyword="lead", kind="exclude"))

    assert repo.list_keywords_by_kind("include") == ["lead"]
    assert repo.list_keywords_by_kind("exclude") == ["lead"]


def test_replace_kind_clears_previous_and_dedupes(tmp_db):
    repo = PreferenceRepository()
    repo.replace_kind("include", ["backend", "python"])

    result = repo.replace_kind("include", ["java", "java", " python "])

    assert result == ["java", "python"]
    assert repo.list_keywords_by_kind("include") == ["java", "python"]
