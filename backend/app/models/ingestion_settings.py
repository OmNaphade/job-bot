from pydantic import BaseModel, Field


class IngestionSettings(BaseModel):
    enable_rss_sources: bool = False
    enable_linkedin_alerts: bool = False
    enable_naukri_alerts: bool = False
    enable_indeed_alerts: bool = False
    allow_direct_scraping: bool = False
    poll_interval_hours: int = Field(default=4, ge=1, le=24)
