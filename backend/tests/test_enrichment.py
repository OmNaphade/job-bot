from app.ingestion.enrichment import clearbit_logo_url, domain_from_url


def test_clearbit_logo_url_builds_from_domain():
    assert clearbit_logo_url("stripe.com") == "https://logo.clearbit.com/stripe.com"


def test_clearbit_logo_url_none_when_no_domain():
    assert clearbit_logo_url(None) is None


def test_domain_from_url_extracts_host():
    assert domain_from_url("https://stripe.com/jobs/search?gh_jid=123") == "stripe.com"


def test_domain_from_url_none_when_no_url():
    assert domain_from_url(None) is None


def test_domain_from_url_excludes_platform_host():
    assert (
        domain_from_url(
            "https://boards.greenhouse.io/figma/jobs/123",
            exclude_hosts=frozenset({"boards.greenhouse.io"}),
        )
        is None
    )


def test_domain_from_url_is_case_insensitive_for_exclusion():
    assert (
        domain_from_url(
            "https://Boards.Greenhouse.io/figma/jobs/123",
            exclude_hosts=frozenset({"boards.greenhouse.io"}),
        )
        is None
    )
