from app.ingestion.adapters.email_parsers import parse_linkedin_alert_email, parse_naukri_alert_email

LINKEDIN_SAMPLE = """
<html><body>
<table><tr><td>
  <a href="https://www.linkedin.com/comm/jobs/view/1234567890/?trk=alert">Backend Engineer</a>
  <div>Acme Corp</div>
  <div>Remote</div>
</td></tr></table>
</body></html>
"""

NAUKRI_SAMPLE = """
<html><body>
<div>
  <a href="https://www.naukri.com/job-listings-python-developer-acme-123456">Python Developer</a>
  <span>Acme India</span>
  <span>Pune</span>
</div>
</body></html>
"""


def test_parse_linkedin_alert_email_extracts_title_company_location():
    jobs = parse_linkedin_alert_email(LINKEDIN_SAMPLE)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].location == "Remote"
    assert jobs[0].source == "linkedin_alerts"


def test_parse_naukri_alert_email_extracts_title_company_location():
    jobs = parse_naukri_alert_email(NAUKRI_SAMPLE)

    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "Acme India"
    assert jobs[0].source == "naukri_alerts"


def test_parse_linkedin_alert_email_ignores_unrelated_links():
    html = '<html><body><a href="https://www.linkedin.com/feed/">Home</a></body></html>'
    assert parse_linkedin_alert_email(html) == []


def test_parse_deduplicates_repeated_links_in_one_email():
    html = """
    <div>
      <a href="https://www.linkedin.com/jobs/view/111/">Engineer A</a>
      <a href="https://www.linkedin.com/jobs/view/111/">Engineer A</a>
    </div>
    """
    assert len(parse_linkedin_alert_email(html)) == 1
