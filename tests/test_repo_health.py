"""Guards the files people edit by hand: a typo in config.yaml or a workflow should fail CI, not production."""

from pathlib import Path

import yaml

from jobalert.config import ROOT, load_config
from jobalert.filters import JobFilter
from jobalert.sources import build_sources

WORKFLOWS = Path(ROOT) / ".github" / "workflows"


def test_shipped_config_loads_and_builds_every_source():
    config = load_config(ROOT / "config.yaml")
    JobFilter(config)  # compiles every keyword pattern
    sources = build_sources(config)
    names = {s.name for s in sources}
    assert {"linkedin", "foundit", "unstop"} <= names
    assert any(n.startswith("greenhouse:") for n in names)
    assert len(names) == len(sources), "source names must be unique (reports and failure tracking key on them)"


def test_config_has_the_filters_that_make_results_good():
    config = load_config(ROOT / "config.yaml")
    keywords = config["keywords"]
    assert keywords["include"] and keywords["exclude"] and keywords["generic_titles"]
    assert config["run"]["max_experience_years"] is not None
    assert config["notify"]["quiet_hours"]["start"] != config["notify"]["quiet_hours"]["end"]


def test_workflows_are_valid_yaml_and_production_runs_every_two_hours():
    for path in WORKFLOWS.glob("*.yml"):
        assert yaml.safe_load(path.read_text(encoding="utf-8")), path.name

    workflow = yaml.safe_load((WORKFLOWS / "jobalert.yml").read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True)  # YAML parses a bare `on` key as boolean True
    cron = triggers["schedule"][0]["cron"]
    minute, hours, *_ = cron.split()
    assert minute == "47" and hours == "1-23/2", "every 2 hours at :17 India time (:47 UTC)"
    assert "workflow_dispatch" in triggers


def test_secrets_never_tracked():
    gitignore = (Path(ROOT) / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines()
    assert "data/" in gitignore.splitlines()
