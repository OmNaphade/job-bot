import pytest

# GitHub Actions (and some shells) export these. Tests must behave the same there as on a laptop, so every
# test starts with them cleared and sets whatever it needs itself.
AMBIENT_VARIABLES = [
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_REPOSITORY",
    "GITHUB_SERVER_URL",
    "GITHUB_EVENT_NAME",
    "GITHUB_STEP_SUMMARY",
    "JOBALERT_CONFIG",
    "JOBALERT_STATE",
    "JOBALERT_RUNLOG",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "ALERT_EMAIL_ADDRESS",
    "ALERT_EMAIL_APP_PASSWORD",
    "ADZUNA_APP_ID",
    "ADZUNA_APP_KEY",
    "JOOBLE_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in AMBIENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
