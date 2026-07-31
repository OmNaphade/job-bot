from app.ingestion.adapters.email_parsers import parse_linkedin_alert_email, parse_naukri_alert_email

# Mirrors the real structure found in a live LinkedIn job-alert-digest email: the
# entire job card (title, "Company (middle dot) Location", then a trailing
# social-proof/status line) sits inside ONE anchor as separate child elements, with
# no HTML separator between them -- get_text("\n") is what splits them into lines.
LINKEDIN_SAMPLE = """
<html><body>
<table><tr><td>
  <a href="https://www.linkedin.com/comm/jobs/view/1234567890/?trackingId=abc123&refId=xyz789">
    <div>Backend Engineer</div>
    <div>Acme Corp · Remote</div>
    <div>1,228 company alumni</div>
  </a>
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


def test_parse_linkedin_alert_email_normalizes_link_and_strips_tracking_params():
    jobs = parse_linkedin_alert_email(LINKEDIN_SAMPLE)

    # Real hrefs carry per-email tracking query strings that would break jobs.link
    # dedup across separate digest emails for the same job -- the job ID is used to
    # build a clean, stable permalink instead of trusting the raw href.
    assert jobs[0].link == "https://www.linkedin.com/jobs/view/1234567890/"


def test_parse_linkedin_alert_email_ignores_trailing_noise_lines():
    html = """
    <a href="https://www.linkedin.com/jobs/view/222/">
      <div>Staff Engineer</div>
      <div>Acme Corp · Pune Division (Hybrid)</div>
      <div>Actively recruiting</div>
      <div>Apply</div>
    </a>
    """
    jobs = parse_linkedin_alert_email(html)

    assert len(jobs) == 1
    assert jobs[0].title == "Staff Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].location == "Pune Division (Hybrid)"


def test_parse_naukri_alert_email_extracts_title_company_location():
    jobs = parse_naukri_alert_email(NAUKRI_SAMPLE)

    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "Acme India"
    assert jobs[0].source == "naukri_alerts"


def test_parse_linkedin_alert_email_ignores_unrelated_links():
    html = '<html><body><a href="https://www.linkedin.com/feed/">Home</a></body></html>'
    assert parse_linkedin_alert_email(html) == []


def test_parse_linkedin_alert_email_skips_icon_only_anchor_with_no_text():
    html = '<a href="https://www.linkedin.com/jobs/view/333/"><img alt="Acme Corp logo"></a>'
    assert parse_linkedin_alert_email(html) == []


def test_parse_deduplicates_repeated_job_id_across_multiple_anchors():
    # Real emails wrap the same job in more than one anchor (e.g. a company-logo
    # anchor and a separate title-text anchor) with DIFFERENT tracking query
    # strings on otherwise-identical hrefs -- dedup must key off the job ID
    # extracted from the URL, not the raw href.
    html = """
    <div>
      <a href="https://www.linkedin.com/jobs/view/111/?trk=logo"><img alt="icon"></a>
      <a href="https://www.linkedin.com/jobs/view/111/?trk=title">
        <div>Engineer A</div>
        <div>Acme Corp · Remote</div>
      </a>
      <a href="https://www.linkedin.com/comm/jobs/view/111/?trk=another">
        <div>Engineer A</div>
        <div>Acme Corp · Remote</div>
      </a>
    </div>
    """
    jobs = parse_linkedin_alert_email(html)
    assert len(jobs) == 1
