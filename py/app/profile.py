"""User profiles: everything that makes scoring personal lives in one TOML file.

Each user has a folder under profiles/<name>/ containing:
  profile.toml   preferences, skills, deal-breakers, scoring weights, model
  resume.md      the resume as plain text (path set in profile.toml)

See profiles/example/ for a template. TOML is read with Python's built-in
tomllib, so no extra dependency is needed.
"""

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

PROFILES_DIR = Path(__file__).resolve().parents[2] / "profiles"


class Candidate(BaseModel):
    name: str
    resume_file: str = "resume.md"
    years_experience: float = Field(ge=0, le=60)


class Preferences(BaseModel):
    target_titles: list[str] = []
    remote_only: bool = False
    locations: list[str] = Field(default=[], description="Acceptable locations if not remote.")
    min_years_required: int | None = Field(
        default=None, description="Skip roles clearly below this seniority."
    )


class Skills(BaseModel):
    must_have: list[str] = Field(default=[], description="Core skills the role should use.")
    nice_to_have: list[str] = []
    avoid: list[str] = Field(default=[], description="Stacks you don't want to work in.")


class DealBreakers(BaseModel):
    keywords: list[str] = Field(
        default=[], description="If any appear in the job text, skip it without calling the LLM."
    )


class Weights(BaseModel):
    """How much each part of the fit counts. Must add up to 100."""

    skills: int = 40
    seniority: int = 20
    domain: int = 20
    preferences: int = 20

    @model_validator(mode="after")
    def _sum_to_100(self) -> "Weights":
        total = self.skills + self.seniority + self.domain + self.preferences
        if total != 100:
            raise ValueError(f"scoring weights must add up to 100, got {total}")
        return self


class LLMSettings(BaseModel):
    provider: str = "gemini"
    model: str | None = None


class Profile(BaseModel):
    candidate: Candidate
    preferences: Preferences = Preferences()
    skills: Skills = Skills()
    deal_breakers: DealBreakers = DealBreakers()
    weights: Weights = Weights()
    llm: LLMSettings = LLMSettings()
    resume: str = Field(default="", description="Filled in from resume_file when loaded.")


class ProfileError(Exception):
    pass


def load_profile(name_or_path: str) -> Profile:
    """Load profiles/<name>/profile.toml (or a direct path to a profile.toml)."""
    path = Path(name_or_path)
    if path.suffix != ".toml":
        path = PROFILES_DIR / name_or_path / "profile.toml"
    if not path.exists():
        raise ProfileError(f"Profile not found: {path}")

    with path.open("rb") as f:
        data = tomllib.load(f)
    try:
        profile = Profile(**data)
    except ValueError as exc:
        raise ProfileError(f"Invalid profile {path}: {exc}") from exc

    resume_path = path.parent / profile.candidate.resume_file
    if not resume_path.exists():
        raise ProfileError(f"Resume file not found: {resume_path}")
    profile.resume = resume_path.read_text()
    return profile
