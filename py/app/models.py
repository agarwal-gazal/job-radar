"""Data shapes for the scoring service.

Pydantic models do two jobs here:
1. They validate what comes into the API.
2. They are the contract for what the LLM must return. We send the JSON
   schema of FitAssessment to the model, then validate its reply against it.

Design choice: the LLM only rates the parts of the fit (skills, seniority,
domain, preferences). The final score is a weighted sum computed in code
using the user's own weights, so the arithmetic is deterministic and each
user can decide what matters most to them.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Job(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    description: str = Field(min_length=20)
    url: str | None = None
    id: str | None = None


class FitAssessment(BaseModel):
    """What the LLM must return for one profile/job pair."""

    skills_score: int = Field(ge=0, le=100, description="How well the candidate's skills match the job's requirements.")
    seniority_score: int = Field(ge=0, le=100, description="How well the candidate's level matches the role's level.")
    domain_score: int = Field(ge=0, le=100, description="How relevant the candidate's industry and problem domain are.")
    preferences_score: int = Field(ge=0, le=100, description="How well the role matches the candidate's stated preferences (titles, location, remote, stacks to avoid).")
    matched_skills: list[str] = Field(description="Skills the job asks for that the resume clearly shows.")
    missing_must_haves: list[str] = Field(
        description="Items from the candidate's must-have list that this job does NOT use. Copy them exactly."
    )
    gaps: list[str] = Field(description="Job requirements the resume does not show.")
    seniority_fit: Literal["under", "match", "over"]
    reasons: str = Field(min_length=10, max_length=600, description="Two or three sentences explaining the fit.")


class FitScore(BaseModel):
    """Final result: the LLM's assessment plus the score computed in code."""

    score: int = Field(ge=0, le=100)
    verdict: Literal["strong", "possible", "weak"]
    components: dict[str, int]
    assessment: FitAssessment


class ScoreRequest(BaseModel):
    profile: str = Field(default="example", description="Name of a folder under profiles/.")
    job: Job


class ScoreResponse(BaseModel):
    job: Job
    profile: str
    skipped: str | None = Field(default=None, description="Why the job was filtered out before scoring.")
    fit: FitScore | None = None
    model: str | None = None
    attempts: int = 0
