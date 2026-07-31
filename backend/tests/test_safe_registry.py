import dataclasses

import app.ingestion.adapters.safe_registry as safe_registry_module
from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.adapters.safe_registry import SafeAdapterRegistry
from app.ingestion.models import JobCandidate
from app.models.ingestion_settings import IngestionSettings


class _FakeAdapter(BaseAdapter):
    def __init__(self, source_name, candidates, enabled=True):
        self.source_name = source_name
        self.enabled = enabled
        self._candidates = candidates

    def fetch(self):
        return self._candidates if self.enabled else []


def _candidate(source: str) -> JobCandidate:
    return JobCandidate(
        title="Engineer", company="Acme", location="Remote", link=f"https://example.com/{source}", source=source
    )


def test_fetch_all_aggregates_candidates_and_tracks_per_source_counts():
    registry = SafeAdapterRegistry()
    registry.register(_FakeAdapter("a", [_candidate("a")]))
    registry.register(_FakeAdapter("b", [_candidate("b1"), _candidate("b2")]))
    registry.register(_FakeAdapter("c", [_candidate("c")], enabled=False))

    candidates = registry.fetch_all()

    assert len(candidates) == 3
    assert registry.last_fetch_counts == {"a": 1, "b": 2, "c": 0}


def _settings(**overrides) -> IngestionSettings:
    defaults = dict(
        enable_rss_sources=False,
        enable_linkedin_alerts=False,
        enable_naukri_alerts=False,
        allow_direct_scraping=False,
        poll_interval_hours=4,
    )
    defaults.update(overrides)
    return IngestionSettings(**defaults)


def test_build_from_settings_registers_one_adapter_per_csv_token(monkeypatch):
    configured = dataclasses.replace(
        safe_registry_module.env_settings,
        greenhouse_board_tokens="stripe, notion",
        lever_company_slugs="",
        ashby_board_names="",
        foundit_search_locations=None,
        foundit_search_queries=None,
    )
    monkeypatch.setattr(safe_registry_module, "env_settings", configured)

    registry = SafeAdapterRegistry.build_from_settings(_settings(allow_direct_scraping=True))

    greenhouse_sources = [a.source_name for a in registry.adapters if a.source_name.startswith("greenhouse:")]
    assert greenhouse_sources == ["greenhouse:stripe", "greenhouse:notion"]


def test_build_from_settings_skips_foundit_without_a_configured_location(monkeypatch):
    configured = dataclasses.replace(
        safe_registry_module.env_settings,
        foundit_search_queries="python,java",
        foundit_search_locations=None,
    )
    monkeypatch.setattr(safe_registry_module, "env_settings", configured)

    registry = SafeAdapterRegistry.build_from_settings(_settings(allow_direct_scraping=True))

    assert not any("foundit" in a.source_name for a in registry.adapters)


def test_build_from_settings_registers_foundit_per_query_when_location_set(monkeypatch):
    configured = dataclasses.replace(
        safe_registry_module.env_settings,
        foundit_search_queries="python, java",
        foundit_search_locations="pune",
    )
    monkeypatch.setattr(safe_registry_module, "env_settings", configured)

    registry = SafeAdapterRegistry.build_from_settings(_settings(allow_direct_scraping=True))

    foundit_sources = [a.source_name for a in registry.adapters if "foundit" in a.source_name.lower()]
    assert len(foundit_sources) == 2


def test_build_from_settings_gates_direct_scraping_sources_on_allow_direct_scraping(monkeypatch):
    configured = dataclasses.replace(safe_registry_module.env_settings, greenhouse_board_tokens="stripe")
    monkeypatch.setattr(safe_registry_module, "env_settings", configured)

    registry = SafeAdapterRegistry.build_from_settings(
        _settings(enable_rss_sources=True, allow_direct_scraping=False)
    )

    greenhouse = next(a for a in registry.adapters if a.source_name == "greenhouse:stripe")
    unstop = next(a for a in registry.adapters if a.source_name == "unstop")
    weworkremotely = next(a for a in registry.adapters if a.source_name == "weworkremotely")
    assert greenhouse.enabled is False
    assert unstop.enabled is False
    assert weworkremotely.enabled is True


def test_build_from_settings_registers_email_alert_adapters_with_both_mailboxes(monkeypatch):
    registry = SafeAdapterRegistry.build_from_settings(_settings(enable_linkedin_alerts=True))

    linkedin = next(a for a in registry.adapters if a.source_name == "linkedin_alerts")
    assert linkedin.enabled is True
    assert linkedin.mailboxes[0] == "INBOX"
