import pytest

from app.core.security import hash_password
from app.models.preference import PreferenceCreate
from app.repositories.preference_repository import PreferenceRepository
from app.repositories.user_repository import UserRepository
from app.services.errors import DuplicateResourceError


def test_create_preference_and_list_by_kind(test_user):
    repo = PreferenceRepository()
    repo.create_preference(test_user.id, PreferenceCreate(keyword="backend", kind="include"))
    repo.create_preference(test_user.id, PreferenceCreate(keyword="senior", kind="exclude"))

    assert repo.list_keywords_by_kind(test_user.id, "include") == ["backend"]
    assert repo.list_keywords_by_kind(test_user.id, "exclude") == ["senior"]


def test_create_preference_raises_on_duplicate_keyword_and_kind(test_user):
    repo = PreferenceRepository()
    repo.create_preference(test_user.id, PreferenceCreate(keyword="backend", kind="include"))
    with pytest.raises(DuplicateResourceError):
        repo.create_preference(test_user.id, PreferenceCreate(keyword="backend", kind="include"))


def test_same_keyword_allowed_across_different_kinds(test_user):
    repo = PreferenceRepository()
    repo.create_preference(test_user.id, PreferenceCreate(keyword="lead", kind="include"))
    repo.create_preference(test_user.id, PreferenceCreate(keyword="lead", kind="exclude"))

    assert repo.list_keywords_by_kind(test_user.id, "include") == ["lead"]
    assert repo.list_keywords_by_kind(test_user.id, "exclude") == ["lead"]


def test_same_keyword_and_kind_allowed_across_different_users(test_user, tmp_db):
    """Regression test for the UNIQUE(user_id, keyword, kind) migration."""
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = PreferenceRepository()

    repo.create_preference(test_user.id, PreferenceCreate(keyword="backend", kind="include"))
    repo.create_preference(other_user.id, PreferenceCreate(keyword="backend", kind="include"))

    assert repo.list_keywords_by_kind(test_user.id, "include") == ["backend"]
    assert repo.list_keywords_by_kind(other_user.id, "include") == ["backend"]


def test_replace_kind_clears_previous_and_dedupes(test_user):
    repo = PreferenceRepository()
    repo.replace_kind(test_user.id, "include", ["backend", "python"])

    result = repo.replace_kind(test_user.id, "include", ["java", "java", " python "])

    assert result == ["java", "python"]
    assert repo.list_keywords_by_kind(test_user.id, "include") == ["java", "python"]


def test_replace_kind_does_not_touch_other_users_preferences(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = PreferenceRepository()
    repo.replace_kind(other_user.id, "include", ["untouched"])

    repo.replace_kind(test_user.id, "include", ["mine"])

    assert repo.list_keywords_by_kind(other_user.id, "include") == ["untouched"]


def test_delete_preference_only_affects_the_owning_user(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = PreferenceRepository()
    mine = repo.create_preference(test_user.id, PreferenceCreate(keyword="backend", kind="include"))

    repo.delete_preference(other_user.id, mine.id)  # wrong owner -- must not delete

    assert repo.list_keywords_by_kind(test_user.id, "include") == ["backend"]
