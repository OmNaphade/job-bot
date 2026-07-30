import logging
from typing import List

from app.core.config import settings as env_settings
from app.ingestion.adapters.ats_adapters import AshbyAdapter, GreenhouseAdapter, LeverAdapter
from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.adapters.email_adapter import EmailAdapter
from app.ingestion.adapters.email_parsers import parse_linkedin_alert_email, parse_naukri_alert_email
from app.ingestion.adapters.remoteok_adapter import RemoteOkAdapter
from app.ingestion.adapters.rss_adapter import RssAdapter
from app.ingestion.models import JobCandidate
from app.models.ingestion_settings import IngestionSettings

logger = logging.getLogger(__name__)


def _split_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


class SafeAdapterRegistry:
    def __init__(self) -> None:
        self.adapters: List[BaseAdapter] = []
        # Populated by fetch_all(): source name -> candidate count from that source's
        # last fetch. Read this after calling fetch_all() for a per-source breakdown.
        self.last_fetch_counts: dict[str, int] = {}

    def register(self, adapter: BaseAdapter) -> None:
        self.adapters.append(adapter)

    def fetch_all(self) -> List[JobCandidate]:
        all_candidates: List[JobCandidate] = []
        self.last_fetch_counts = {}
        for adapter in self.adapters:
            source_name = getattr(adapter, "source_name", adapter.__class__.__name__)
            enabled = getattr(adapter, "enabled", True)
            candidates = adapter.fetch()
            self.last_fetch_counts[source_name] = len(candidates)
            if enabled:
                logger.info("Source '%s': checked, fetched %d candidate(s)", source_name, len(candidates))
            else:
                logger.info("Source '%s': disabled, skipped", source_name)
            all_candidates.extend(candidates)
        logger.info(
            "Checked %d source(s) (%d enabled): %s",
            len(self.adapters),
            sum(1 for a in self.adapters if getattr(a, "enabled", True)),
            ", ".join(f"{name}={count}" for name, count in self.last_fetch_counts.items()),
        )
        return all_candidates

    @classmethod
    def build_from_settings(cls, settings: IngestionSettings) -> "SafeAdapterRegistry":
        registry = cls()
        registry.register(
            RssAdapter("weworkremotely", env_settings.weworkremotely_feed_url, enabled=settings.enable_rss_sources)
        )
        registry.register(RssAdapter("himalayas", env_settings.himalayas_feed_url, enabled=settings.enable_rss_sources))
        registry.register(RssAdapter("unstop", env_settings.unstop_feed_url, enabled=settings.enable_rss_sources))
        registry.register(RssAdapter("foundit", env_settings.foundit_feed_url, enabled=settings.enable_rss_sources))
        registry.register(RssAdapter("remotive", env_settings.remotive_feed_url, enabled=settings.enable_rss_sources))
        registry.register(RssAdapter("nodesk", env_settings.nodesk_feed_url, enabled=settings.enable_rss_sources))
        registry.register(
            RssAdapter("jobspresso", env_settings.jobspresso_feed_url, enabled=settings.enable_rss_sources)
        )
        registry.register(RemoteOkAdapter(env_settings.remoteok_api_url, enabled=settings.enable_rss_sources))
        for token in _split_csv(env_settings.greenhouse_board_tokens):
            registry.register(GreenhouseAdapter(token, enabled=settings.allow_direct_scraping))
        for slug in _split_csv(env_settings.lever_company_slugs):
            registry.register(LeverAdapter(slug, enabled=settings.allow_direct_scraping))
        for name in _split_csv(env_settings.ashby_board_names):
            registry.register(AshbyAdapter(name, enabled=settings.allow_direct_scraping))
        registry.register(
            EmailAdapter(
                "linkedin_alerts",
                sender=env_settings.linkedin_alert_sender,
                parser=parse_linkedin_alert_email,
                enabled=settings.enable_linkedin_alerts,
            )
        )
        registry.register(
            EmailAdapter(
                "naukri_alerts",
                sender=env_settings.naukri_alert_sender,
                parser=parse_naukri_alert_email,
                enabled=settings.enable_naukri_alerts,
            )
        )
        return registry
