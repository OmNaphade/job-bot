import logging

from ..config import env
from . import ats, remote_boards, telegram_channels
from .aggregators import Adzuna, Jooble
from .base import Source
from .email_alerts import EmailAlerts
from .linkedin import LinkedIn
from .portals import Foundit, Unstop

log = logging.getLogger(__name__)


def build_sources(config: dict) -> list[Source]:
    """Turns the `sources:` section of config.yaml into source objects.

    A source whose section is missing/disabled, or whose credentials aren't set, is skipped.
    """
    cfg = config["sources"]
    sources: list[Source] = []

    def section(name: str) -> dict | None:
        value = cfg.get(name)
        return value if isinstance(value, dict) and value.get("enabled", True) else None

    if (s := section("linkedin")) and s.get("searches"):
        sources.append(LinkedIn(s))

    if s := section("email_alerts"):
        address, password = env("ALERT_EMAIL_ADDRESS"), env("ALERT_EMAIL_APP_PASSWORD").replace(" ", "")
        if address and password:
            sources.append(EmailAlerts(s, address, password))
        else:
            log.info("email_alerts: ALERT_EMAIL_ADDRESS / ALERT_EMAIL_APP_PASSWORD not set, skipping")

    if (s := section("foundit")) and s.get("queries"):
        sources.append(Foundit(s))
    if s := section("unstop"):
        sources.append(Unstop(s))

    if s := section("adzuna"):
        app_id, app_key = env("ADZUNA_APP_ID"), env("ADZUNA_APP_KEY")
        if app_id and app_key and s.get("queries"):
            sources.append(Adzuna(s, app_id, app_key))
    if s := section("jooble"):
        if env("JOOBLE_API_KEY") and s.get("queries"):
            sources.append(Jooble(s, env("JOOBLE_API_KEY")))

    if s := section("remote_boards"):
        sources.extend(remote_boards.build(s))
    if s := section("company_boards"):
        sources.extend(ats.build(s))
    if s := section("telegram_channels"):
        sources.extend(telegram_channels.build(s.get("channels", [])))

    return sources
