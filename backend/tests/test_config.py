import importlib

from app.core import config as config_module


def _reload_settings_with_env(monkeypatch, **env_vars):
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    reloaded = importlib.reload(config_module)
    return reloaded.settings


def test_empty_string_env_var_falls_back_to_default(monkeypatch):
    # GitHub Actions sets an env var to "" (not unset) when it references a
    # secrets.X that doesn't exist -- plain os.getenv(name, default) would
    # wrongly return "" instead of the default, which crashed int(imap_port).
    settings = _reload_settings_with_env(
        monkeypatch,
        ALERT_EMAIL_IMAP_PORT="",
        ALERT_EMAIL_IMAP_HOST="",
        WEWORKREMOTELY_FEED_URL="",
        HIMALAYAS_FEED_URL="",
    )

    assert settings.alert_email_imap_port == 993
    assert settings.alert_email_imap_host == "imap.gmail.com"
    assert settings.weworkremotely_feed_url == "https://weworkremotely.com/categories/remote-programming-jobs.rss"
    assert settings.himalayas_feed_url == "https://himalayas.app/jobs/rss"


def test_empty_string_env_var_is_treated_as_none_for_optional_fields(monkeypatch):
    settings = _reload_settings_with_env(monkeypatch, TELEGRAM_BOT_TOKEN="", UNSTOP_FEED_URL="")

    assert settings.telegram_bot_token is None
    assert settings.unstop_feed_url is None


def test_real_value_still_wins_over_default(monkeypatch):
    settings = _reload_settings_with_env(monkeypatch, ALERT_EMAIL_IMAP_PORT="2993")

    assert settings.alert_email_imap_port == 2993
