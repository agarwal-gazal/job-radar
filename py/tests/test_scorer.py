"""Tests for scoring: retry-and-repair and weighted scores, using a fake LLM (no API key, no network)."""

import json

import pytest

from app.models import Job
from app.profile import Candidate, Profile, Skills, Weights
from app.scorer import MAX_ATTEMPTS, ScoringError, score_fit

PROFILE = Profile(
    candidate=Candidate(name="Test", years_experience=7),
    skills=Skills(must_have=["Python", "RAG"]),
    weights=Weights(skills=40, seniority=20, domain=20, preferences=20),
    resume="Software Engineer, 7 years. Python, Django, RAG, Qdrant, MCP.",
)
JOB = Job(
    title="Senior AI Engineer",
    company="ExampleCo",
    description="We need 6+ years of Python, RAG and vector databases, FastAPI and LangGraph.",
)

GOOD = {
    "skills_score": 80,
    "seniority_score": 90,
    "domain_score": 70,
    "preferences_score": 60,
    "matched_skills": ["Python", "RAG"],
    "missing_must_haves": [],
    "gaps": ["FastAPI", "LangGraph"],
    "seniority_fit": "match",
    "reasons": "Strong Python and RAG overlap; FastAPI and LangGraph are missing.",
}


class FakeLLM:
    """Returns canned replies in order and records the prompts it received."""

    model_name = "fake"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, schema: dict) -> str:
        self.prompts.append(prompt)
        return self.replies[len(self.prompts) - 1]


def test_weighted_score_uses_profile_weights():
    fit, attempts = score_fit(FakeLLM([json.dumps(GOOD)]), PROFILE, JOB)
    # 80*0.4 + 90*0.2 + 70*0.2 + 60*0.2 = 32 + 18 + 14 + 12 = 76
    assert (fit.score, fit.verdict, attempts) == (76, "strong", 1)


def test_different_weights_change_the_score():
    skills_first = PROFILE.model_copy(update={"weights": Weights(skills=70, seniority=10, domain=10, preferences=10)})
    fit, _ = score_fit(FakeLLM([json.dumps(GOOD)]), skills_first, JOB)
    # 80*0.7 + 90*0.1 + 70*0.1 + 60*0.1 = 56 + 9 + 7 + 6 = 78
    assert fit.score == 78


def test_prompt_includes_profile_preferences():
    llm = FakeLLM([json.dumps(GOOD)])
    score_fit(llm, PROFILE, JOB)
    assert "Must-have skills: Python, RAG" in llm.prompts[0]


def test_repairs_malformed_json():
    llm = FakeLLM(["not json at all", json.dumps(GOOD)])
    _, attempts = score_fit(llm, PROFILE, JOB)
    assert attempts == 2
    assert "Validation error" in llm.prompts[1]


def test_repairs_out_of_range_component():
    bad = {**GOOD, "skills_score": 120}
    _, attempts = score_fit(FakeLLM([json.dumps(bad), json.dumps(GOOD)]), PROFILE, JOB)
    assert attempts == 2


def test_rejects_invented_must_haves():
    bad = {**GOOD, "missing_must_haves": ["Rust"]}
    llm = FakeLLM([json.dumps(bad), json.dumps(GOOD)])
    _, attempts = score_fit(llm, PROFILE, JOB)
    assert attempts == 2
    assert "not on it" in llm.prompts[1]


def test_gives_up_after_max_attempts():
    llm = FakeLLM(["{}"] * MAX_ATTEMPTS)
    with pytest.raises(ScoringError):
        score_fit(llm, PROFILE, JOB)
    assert len(llm.prompts) == MAX_ATTEMPTS
