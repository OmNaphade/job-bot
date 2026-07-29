from typing import List

from app.core.config import settings as env_settings
from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.adapters.email_adapter import EmailAdapter
from app.ingestion.adapters.email_parsers import parse_linkedin_alert_email, parse_naukri_alert_email
from app.ingestion.adapters.remoteok_adapter import RemoteOkAdapter
from app.ingestion.adapters.rss_adapter import RssAdapter
from app.ingestion.models import JobCandidate
from app.models.ingestion_settings import IngestionSettings


class SafeAdapterRegistry:
    def __init__(self) -> None:
        self.adapters: List[BaseAdapter] = []

    def register(self, adapter: BaseAdapter) -> None:
        self.adapters.append(adapter)

    def fetch_all(self) -> List[JobCandidate]:
        all_candidates: List[JobCandidate] = []
        for adapter in self.adapters:
            all_candidates.extend(adapter.fetch())
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
