"""Tests for loading profiles and the free rule-based prefilter."""

import pytest

from app.models import Job
from app.prefilter import prefilter
from app.profile import (
    Candidate,
    DealBreakers,
    Preferences,
    Profile,
    ProfileError,
    Skills,
    Weights,
    load_profile,
)


def make_profile(**overrides) -> Profile:
    base = dict(
        candidate=Candidate(name="Test", years_experience=5),
        preferences=Preferences(remote_only=True),
        skills=Skills(avoid=["Salesforce", ".NET"]),
        deal_breakers=DealBreakers(keywords=["commission only"]),
        resume="resume text",
    )
    base.update(overrides)
    return Profile(**base)


def job(title: str, description: str = "A normal backend role using Python and PostgreSQL.") -> Job:
    return Job(title=title, company="Co", description=description)


def test_example_profile_loads():
    profile = load_profile("example")
    assert profile.candidate.name == "Alex Example"
    assert "Backend Engineer" in profile.resume


def test_missing_profile_raises():
    with pytest.raises(ProfileError):
        load_profile("does-not-exist")


def test_weights_must_sum_to_100():
    with pytest.raises(ValueError):
        Weights(skills=50, seniority=50, domain=50, preferences=50)


def test_normal_job_passes():
    assert prefilter(job("Senior Backend Engineer"), make_profile()) is None


def test_deal_breaker_keyword_skips():
    reason = prefilter(job("Sales Engineer", "This role is commission only, fully remote."), make_profile())
    assert reason and "deal-breaker" in reason


def test_avoided_stack_in_title_skips_including_dotnet():
    assert prefilter(job("Full-Stack .NET Developer"), make_profile())
    assert prefilter(job("Salesforce Developer"), make_profile())


def test_avoid_list_does_not_match_inside_other_words():
    # ".NET" must not match "internet" or "dotnetting"
    assert prefilter(job("Backend Engineer, Internet Platform"), make_profile()) is None


def test_onsite_role_skipped_for_remote_only_user():
    onsite = job("Backend Engineer", "This is a work from office role in Pune, five days a week.")
    assert prefilter(onsite, make_profile())
    flexible = make_profile(preferences=Preferences(remote_only=False, locations=["Pune"]))
    assert prefilter(onsite, flexible) is None
