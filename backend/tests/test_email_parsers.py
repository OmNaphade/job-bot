from app.ingestion.adapters.email_parsers import (
    parse_indeed_alert_email,
    parse_linkedin_alert_email,
    parse_naukri_alert_email,
)

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

# Mirrors the real structure found in a live Indeed job-alert-digest email: each
# job is a <table class="width-100"> card containing a title anchor (href carries
# a `jk=<job key>` tracking query param) followed by plain <p> company/location
# text within the same card, plus trailing noise ("Easily apply", a posted-date
# line) after them.
INDEED_SAMPLE = """
<html><body>
<table class="width-100">
  <tr><td><h2><a href="https://in.indeed.com/rc/clk/dl?jk=abc123def456&from=ja&tk=xyz">Backend Engineer</a></h2></td></tr>
  <tr><td><p>Acme Corp</p></td></tr>
  <tr><td><p>Remote</p></td></tr>
  <tr><td><p>Easily apply</p></td></tr>
  <tr><td><p>Posted 2 days ago</p></td></tr>
</table>
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


def test_parse_indeed_alert_email_extracts_title_company_location():
    jobs = parse_indeed_alert_email(INDEED_SAMPLE)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].location == "Remote"
    assert jobs[0].source == "indeed_alerts"


def test_parse_indeed_alert_email_builds_clean_link_from_job_key():
    # Real hrefs carry heavy per-email tracking query strings (tk/alid/bb/qd/rd)
    # that would produce a different `link` for the same job across separate
    # digest emails and break dedup (`jobs.link UNIQUE`) -- the `jk` job key is
    # extracted and used to build a clean, stable permalink instead.
    jobs = parse_indeed_alert_email(INDEED_SAMPLE)

    assert jobs[0].link == "https://in.indeed.com/viewjob?jk=abc123def456"


def test_parse_indeed_alert_email_ignores_unrelated_links():
    html = '<html><body><a href="https://in.indeed.com/jobs?q=python">Search</a></body></html>'
    assert parse_indeed_alert_email(html) == []


def test_parse_indeed_alert_email_deduplicates_repeated_job_key():
    html = """
    <table class="width-100">
      <tr><td><h2><a href="https://in.indeed.com/rc/clk/dl?jk=dup1&tk=a">Engineer A</a></h2></td></tr>
      <tr><td><p>Acme Corp</p></td></tr>
      <tr><td><p>Remote</p></td></tr>
    </table>
    <table class="width-100">
      <tr><td><h2><a href="https://in.indeed.com/rc/clk/dl?jk=dup1&tk=b">Engineer A</a></h2></td></tr>
      <tr><td><p>Acme Corp</p></td></tr>
      <tr><td><p>Remote</p></td></tr>
    </table>
    """
    jobs = parse_indeed_alert_email(html)
    assert len(jobs) == 1


def test_parse_indeed_alert_email_handles_multiple_cards():
    html = """
    <table class="width-100">
      <tr><td><h2><a href="https://in.indeed.com/rc/clk/dl?jk=aaa111&tk=a">Engineer A</a></h2></td></tr>
      <tr><td><p>Acme Corp</p></td></tr>
      <tr><td><p>Remote</p></td></tr>
    </table>
    <table class="width-100">
      <tr><td><h2><a href="https://in.indeed.com/rc/clk/dl?jk=bbb222&tk=b">Engineer B</a></h2></td></tr>
      <tr><td><p>Other Corp</p></td></tr>
      <tr><td><p>Bengaluru</p></td></tr>
    </table>
    """
    jobs = parse_indeed_alert_email(html)
    assert len(jobs) == 2
    assert {job.title for job in jobs} == {"Engineer A", "Engineer B"}
