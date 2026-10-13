from datetime import datetime, timedelta, timezone

from jobalert.filters import JobFilter
from jobalert.models import Job
from jobalert.notify import chunk_digest, format_job
from jobalert.sources.base import Source
from jobalert.store import State
from jobalert.util import canonical_url, fingerprint, infer_experience, infer_required_experience, parse_dt

NOW = datetime.now(timezone.utc)


class FakeSource(Source):
    def __init__(self, jobs=(), *, prefiltered=False, geo_targeted=False, name="fake"):
        self.name, self.jobs = name, list(jobs)
        self.prefiltered, self.geo_targeted = prefiltered, geo_targeted

    def fetch(self):
        return self.jobs


def make_job(title="Python Developer", company="Acme", location="Pune, India", link="https://x.test/1", **kw):
    return Job(title=title, company=company, location=location, link=link, source="fake", **kw)


CONFIG = {
    "keywords": {"include": ["python", "java", "spring boot"], "exclude": ["senior", "sr", "lead"], "boost": ["kafka"]},
    "location": {"allow": ["india", "remote"], "preferred": ["pune"]},
    "run": {"max_age_days": 3, "max_experience_years": 3},
}


# ---------------------------------------------------------------- util

def test_canonical_url_strips_tracking_but_keeps_identity():
    url = "https://www.indeed.com/viewjob?jk=abc123&utm_source=mail&tk=zzz#frag"
    assert canonical_url(url) == "https://www.indeed.com/viewjob?jk=abc123"
    assert canonical_url("https://a.test/jobs/1/?refId=9") == canonical_url("https://a.test/jobs/1")


def test_fingerprint_matches_same_role_across_sources():
    a = fingerprint("Python Developer", "Acme Pvt. Ltd", "Pune Division, Maharashtra, India")
    b = fingerprint("python  developer", "Acme Pvt Ltd", "Pune, Maharashtra")
    assert a == b
    assert a != fingerprint("Python Developer", "Acme Pvt Ltd", "Mumbai, Maharashtra")


def test_parse_dt_handles_common_shapes():
    assert parse_dt("2026-10-13") == datetime(2026, 10, 13, tzinfo=timezone.utc)
    assert parse_dt(1791869667000) == parse_dt(1791869667)
    assert parse_dt("Tue, 13 Oct 2026 10:00:00 +0000").year == 2026
    assert parse_dt("garbage") is None and parse_dt(None) is None


# ---------------------------------------------------------------- filters

def test_include_is_whole_word_and_exclude_checks_title_only():
    f = JobFilter(CONFIG)
    source = FakeSource()
    assert f.check(make_job("Python Developer"), source).keep
    assert not f.check(make_job("JavaScript Developer"), source).keep  # "java" must not match "JavaScript"
    assert f.check(make_job("Sr. Python Developer"), source).reason == "excluded keyword"
    assert f.check(make_job("Backend Dev", extra="python spring boot"), source).keep  # skills text counts


def test_prefiltered_sources_skip_include_but_not_exclude():
    f = JobFilter(CONFIG)
    source = FakeSource(prefiltered=True)
    assert f.check(make_job("Data Wrangler"), source).keep
    assert not f.check(make_job("Lead Wrangler"), source).keep


def test_location_only_checked_for_untargeted_sources():
    f = JobFilter(CONFIG)
    job = make_job(location="USA Only")
    assert f.check(job, FakeSource()).reason == "location"
    assert f.check(job, FakeSource(geo_targeted=True)).keep
    assert f.check(make_job(location="Unknown"), FakeSource()).keep


def test_age_and_experience_limits():
    f = JobFilter(CONFIG)
    source = FakeSource()
    assert f.check(make_job(posted_at=NOW - timedelta(days=5)), source).reason == "too old"
    assert f.check(make_job(posted_at=NOW - timedelta(hours=5)), source).keep
    assert f.check(make_job(min_exp=5), source).reason == "experience"
    assert f.check(make_job(min_exp=2, max_exp=5), source).keep


def test_score_prefers_title_hits_fresh_and_preferred_city():
    f = JobFilter(CONFIG)
    strong = make_job("Java Spring Boot Developer", location="Pune", extra="kafka", posted_at=NOW - timedelta(hours=1))
    weak = make_job("Backend Dev", location="Delhi", extra="python", posted_at=NOW - timedelta(days=2))
    assert f.score(strong, NOW) > f.score(weak, NOW)


# ---------------------------------------------------------------- state

def test_state_roundtrip_dedup_and_failure_tracking(tmp_path):
    path = tmp_path / "state.json"
    state = State(path)
    assert not state.initialized
    job = make_job()
    assert not state.has_seen(job)
    state.mark_seen(job)
    state.initialized = True
    state.failures["linkedin"] = 2
    state.save()

    again = State(path)
    assert again.initialized and again.failures == {"linkedin": 2}
    assert again.has_seen(job)
    # Same role arriving from another site with a different URL is still recognised.
    assert again.has_seen(make_job(link="https://other.test/abc", location="Pune"))


def test_corrupt_state_file_acts_like_first_run(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    assert not State(path).initialized


def test_state_prunes_old_entries(tmp_path):
    state = State(tmp_path / "state.json")
    state.seen = {"old": "2020-01-01T00:00:00+00:00", "new": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    state.save()
    assert set(State(tmp_path / "state.json").seen) == {"new"}


# ---------------------------------------------------------------- messages

def test_format_job_escapes_html_and_shows_facts():
    job = make_job("C++ <Dev> & Co", min_exp=1, max_exp=3, salary="₹6-9 LPA", posted_at=NOW - timedelta(hours=2))
    text = format_job(job, hot=True)
    assert "&lt;Dev&gt; &amp; Co" in text and "1-3 yrs" in text and "₹6-9 LPA" in text and "2h ago" in text
    assert text.startswith("🔥")


def test_digest_is_chunked_under_telegram_limit():
    jobs = [make_job(f"Python Developer {i}", link=f"https://x.test/{i}") for i in range(200)]
    chunks = list(chunk_digest(jobs))
    assert len(chunks) > 1
    assert all(len(text) < 4096 for _, text in chunks)
    assert sum(len(c) for c, _ in chunks) == 200


def test_infer_experience_from_text():
    assert infer_experience("Java Developer (2-4 yrs)") == (2.0, 4.0)
    assert infer_experience("Backend Engineer 5+ years") == (5.0, None)
    assert infer_experience("Java Dev", "Experience: 0 to 1 years in Spring") == (0.0, 1.0)
    # a company boast in a description is not a requirement
    assert infer_experience("Java Dev", "We have 10+ years of excellence") == (None, None)
    assert make_job("Java Developer 3-5 years").min_exp == 3.0
    assert make_job("Java Developer", min_exp=0).min_exp == 0


def test_title_experience_beats_source_field_and_text_is_cleaned():
    assert make_job("Java Developer_2-4 Yrs_Indore").min_exp == 2.0
    assert make_job("MuleSoft Dev || 5-7 Yrs ||", min_exp=0).min_exp == 5.0
    job = make_job("PHP &#038; React", location="Hyderabad, Telangana, Telangana, India")
    assert job.title == "PHP & React"
    assert job.location == "Hyderabad, Telangana, India"


def test_skills_rank_but_never_qualify():
    cfg = {**CONFIG, "keywords": {**CONFIG["keywords"], "boost": [], "skills": ["docker", "kafka", "ci/cd"]}}
    f = JobFilter(cfg)
    plain = make_job("Python Developer", extra="")
    rich = make_job("Python Developer", extra="Docker Kafka CI/CD")
    assert f.score(rich, NOW) == f.score(plain, NOW) + 3
    # a job whose only link to you is a generic skill is still rejected
    assert f.check(make_job("Data Analyst", extra="docker"), FakeSource()).keep is False


GENERIC = {
    **CONFIG,
    "keywords": {**CONFIG["keywords"], "generic_titles": ["associate engineer", "analyst", "engineer"],
                 "skills": ["docker", "sql"]},
}


def test_generic_title_needs_proof_in_the_description():
    f = JobFilter(GENERIC)
    source = FakeSource()
    proven = make_job("Associate Engineer", extra="We build Java services with Spring Boot and SQL")
    assert f.check(proven, source).keep
    # one passing mention is not proof, and a business role with no stack is out
    assert not f.check(make_job("Associate Engineer", extra="nice to have: java"), source).keep
    assert not f.check(make_job("Business Analyst", extra="Excel reporting, SQL"), source).keep
    # a title that isn't a generic one never gets in on description alone
    assert not f.check(make_job("Sales Executive", extra="java spring boot docker"), source).keep


def test_unread_description_defers_the_keyword_gate():
    f = JobFilter(GENERIC)
    assert f.check(make_job("Associate Engineer"), FakeSource(), final=False).keep
    assert not f.check(make_job("Associate Engineer"), FakeSource(), final=True).keep


def test_required_experience_from_descriptions():
    assert infer_required_experience("We need 0-2 years of experience in Java") == (0.0, 2.0)
    assert infer_required_experience("Minimum 3+ years experience with Spring") == (3.0, None)
    assert infer_required_experience("Experience: 2 years in backend") == (2.0, None)
    # company boasts and unrelated durations are not requirements
    assert infer_required_experience("With 20 years of experience in payments, Nium...") == (None, None)
    assert infer_required_experience("Over 5 years of experience serving clients") == (None, None)
    assert infer_required_experience("This is a 6 month contract. Freshers welcome") == (None, None)


# ---------------------------------------------------------------- companies, regions, salary

UPGRADED = {
    "keywords": {"include": ["java"], "exclude": []},
    "companies": {"exclude": ["Shady Staffing"], "prefer": ["Acme"]},
    "location": {"allow": ["india", "remote", "anywhere"], "exclude": ["us only", "mexico", "europe"], "preferred": []},
    "run": {"max_age_days": 3, "min_salary_lpa": 4},
}


def test_company_blocklist_and_preference():
    f = JobFilter(UPGRADED)
    assert f.check(make_job("Java Dev", company="Shady Staffing Pvt Ltd"), FakeSource()).reason == "excluded company"
    assert f.score(make_job("Java Dev", company="Acme Corp"), NOW) == f.score(make_job("Java Dev", company="Other"), NOW) + 3


def test_region_locked_remote_jobs_are_dropped_unless_open_to_india():
    f = JobFilter(UPGRADED)
    source = FakeSource()
    assert f.check(make_job("Java Dev (Remote, Mexico)", location="Remote"), source).reason == "region-locked"
    assert f.check(make_job("Java Dev", location="Remote - US only"), source).reason == "region-locked"
    assert f.check(make_job("Java Dev", location="Remote, Europe or India"), source).keep
    assert f.check(make_job("Java Dev", location="Anywhere"), source).keep
    # a place you searched for yourself is never second-guessed
    assert f.check(make_job("Java Dev (Remote, Mexico)", location="Remote"), FakeSource(geo_targeted=True)).keep


def test_minimum_salary_only_applies_when_a_salary_is_stated():
    f = JobFilter(UPGRADED)
    assert f.check(make_job("Java Dev", salary_lpa=2.5), FakeSource()).reason == "salary"
    assert f.check(make_job("Java Dev", salary_lpa=6), FakeSource()).keep
    assert f.check(make_job("Java Dev"), FakeSource()).keep  # unknown salary is not a reason to drop it
