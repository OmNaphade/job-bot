from jobalert.sources.email_alerts import parse_indeed, parse_linkedin, parse_naukri
from jobalert.sources.linkedin import parse_cards
from jobalert.sources.telegram_channels import parse_channel

LINKEDIN_SEARCH = """
<li><div class="base-card base-search-card job-search-card" data-entity-urn="urn:li:jobPosting:4476069840">
  <a class="base-card__full-link" href="https://in.linkedin.com/jobs/view/sr-python-4476069840?position=1&trackingId=x"></a>
  <div class="base-search-card__info">
    <h3 class="base-search-card__title">
      Python Developer
    </h3>
    <h4 class="base-search-card__subtitle"><a>Acme Corp</a></h4>
    <div class="base-search-card__metadata">
      <span class="job-search-card__location">Pune Division, Maharashtra, India</span>
      <time class="job-search-card__listdate--new" datetime="2026-10-13">2 hours ago</time>
    </div>
  </div>
</div></li>
<li><div class="base-card base-search-card" data-entity-urn="urn:li:jobPosting:1">
  <div class="base-search-card__info"><h3 class="base-search-card__title">No Company Job</h3></div></div></li>
"""


def test_linkedin_search_cards():
    jobs = parse_cards(LINKEDIN_SEARCH)
    assert [j.title for j in jobs] == ["Python Developer", "No Company Job"]
    first = jobs[0]
    assert first.link == "https://www.linkedin.com/jobs/view/4476069840"
    assert first.company == "Acme Corp" and first.location == "Pune Division, Maharashtra, India"
    assert first.posted_at.year == 2026
    assert jobs[1].company == "Unknown"


def test_linkedin_alert_email_uses_clean_permalink_and_skips_icon_anchors():
    html = """
    <a href="https://www.linkedin.com/comm/jobs/view/123456?trackingId=abc"><img src="x.png"></a>
    <a href="https://www.linkedin.com/comm/jobs/view/123456?trackingId=abc">Backend Engineer<br>Acme · Pune, India<br>Actively recruiting</a>
    """
    jobs = parse_linkedin(html)
    assert len(jobs) == 1
    assert (jobs[0].title, jobs[0].company, jobs[0].location) == ("Backend Engineer", "Acme", "Pune, India")
    assert jobs[0].link == "https://www.linkedin.com/jobs/view/123456"


def test_indeed_alert_email_keys_on_job_key():
    html = """<table class="width-100"><tr><td>
      <a href="https://in.indeed.com/rc/clk?jk=abc123&tk=zzz">Java Developer</a><br>
      <div>Acme Pvt Ltd</div><div>Pune, Maharashtra</div></td></tr></table>"""
    jobs = parse_indeed(html)
    assert len(jobs) == 1
    assert (jobs[0].company, jobs[0].location) == ("Acme Pvt Ltd", "Pune, Maharashtra")
    assert jobs[0].link == "https://in.indeed.com/viewjob?jk=abc123"


def test_naukri_alert_email_best_effort():
    html = """<td><a href="https://www.naukri.com/job-listings-python-developer-acme-pune-1-to-3-years-123">Python Developer</a>
    <div>Acme</div><div>Pune</div></td>"""
    jobs = parse_naukri(html)
    assert len(jobs) == 1 and jobs[0].title == "Python Developer"


CHANNEL = """
<div class="tgme_widget_message" data-post="jobs_chan/42">
  <div class="tgme_widget_message_text">Python Developer Fresher - Acme<br>Pune | 0-1 yrs<br>
    Apply: <a href="https://acme.test/careers/1">link</a> or <a href="https://t.me/jobs_chan">channel</a></div>
  <a class="tgme_widget_message_date"><time datetime="2026-10-13T08:00:00+00:00"></time></a>
</div>
<div class="tgme_widget_message" data-post="jobs_chan/43"><div class="tgme_widget_message_photo"></div></div>
"""


def test_telegram_channel_posts_become_jobs():
    jobs = parse_channel(CHANNEL, "jobs_chan", "telegram:jobs_chan")
    assert len(jobs) == 1  # the photo-only post has no text
    job = jobs[0]
    assert job.title == "Python Developer Fresher - Acme"
    assert job.link == "https://acme.test/careers/1"  # outbound apply link, not the t.me channel link
    assert "Pune" in job.extra and job.posted_at is not None


def test_linkedin_detail_page_gives_description_and_seniority():
    from jobalert.sources.linkedin import parse_detail

    html = """
    <div class="show-more-less-html__markup"><p>Build services.</p><ul><li>0-2 years of experience</li></ul></div>
    <ul><li class="description__job-criteria-item">
      <h3 class="description__job-criteria-subheader">Seniority level</h3>
      <span class="description__job-criteria-text">Entry level</span></li></ul>"""
    description, seniority = parse_detail(html)
    assert "0-2 years of experience" in description and seniority == "Entry level"
    assert parse_detail("<html></html>") == ("", "")


def test_linkedin_stops_searching_once_it_is_clearly_blocked(monkeypatch):
    from jobalert.sources import linkedin
    from jobalert.util import FetchError

    calls = []

    def blocked(*args, **kwargs):
        calls.append(1)
        raise FetchError("429")

    monkeypatch.setattr(linkedin, "get", blocked)
    monkeypatch.setattr(linkedin.time, "sleep", lambda _: None)
    source = linkedin.LinkedIn({"searches": [{"keywords": f"q{i}"} for i in range(8)]})
    try:
        source.fetch()
        raised = False
    except FetchError:
        raised = True
    assert raised and len(calls) == 2  # gave up after two refusals instead of trying all eight
