import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def env(name: str) -> str:
    """Env var, treating set-but-empty (what GitHub Actions gives for a missing secret) as unset."""
    return (os.getenv(name) or "").strip()


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    load_dotenv(ROOT / ".env")
    config_path = Path(path or env("JOBALERT_CONFIG") or ROOT / "config.yaml")
    with open(config_path, encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    for section in ("keywords", "location", "sources", "notify", "run"):
        config[section] = config.get(section) or {}
    return config
