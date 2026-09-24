"""Scores how well a user's profile fits a job, using an LLM with validated output.

The key idea (and a good interview talking point): LLM output is untrusted.
Even with a JSON schema, a reply can be malformed or break a rule. So we:

1. ask for JSON matching FitAssessment's schema,
2. validate the reply with Pydantic (types, 0-100 ranges, allowed values),
3. check rules the schema can't express (e.g. "missing must-haves" must come
   from the user's own must-have list, so the model can't invent them),
4. if anything fails, send the exact error back and ask the model to repair
   its answer ("retry-and-repair"), up to MAX_ATTEMPTS times,
5. compute the final score in code from the user's weights.
"""

import json
from typing import Protocol

from pydantic import ValidationError

from .models import FitAssessment, FitScore, Job
from .profile import Profile, Weights

MAX_ATTEMPTS = 3


class LLMClient(Protocol):
    """Anything that can turn a prompt + JSON schema into a text reply.

    The real implementation calls Gemini (see llm.py); tests use a fake.
    Keeping this as an interface means we can swap providers later.
    """

    model_name: str

    def generate_json(self, prompt: str, schema: dict) -> str: ...


class ScoringError(Exception):
    """Raised when the LLM never produced a valid assessment."""


def _list(items: list[str]) -> str:
    return ", ".join(items) if items else "(none given)"


def build_prompt(profile: Profile, job: Job) -> str:
    p, s = profile.preferences, profile.skills
    where = "remote only" if p.remote_only else f"remote or {_list(p.locations)}"
    return f"""You are a strict technical recruiter rating how well a candidate fits a job.
Judge only from the text below. Do not invent experience the resume does not show.

Rate each part from 0 to 100:
- skills_score: overlap between the job's requirements and the resume, weighting the must-have skills most.
- seniority_score: the candidate has {profile.candidate.years_experience:g} years of experience; compare with what the role asks for.
- domain_score: relevance of the candidate's industry and problem domain.
- preferences_score: fit with the candidate's preferences below.

Also return matched_skills, gaps, seniority_fit and 2-3 sentences of reasons.
missing_must_haves: copy exactly the items from the must-have list that this job does not use.

=== CANDIDATE PREFERENCES ===
Target titles: {_list(p.target_titles)}
Location: {where}
Must-have skills: {_list(s.must_have)}
Nice-to-have skills: {_list(s.nice_to_have)}
Stacks to avoid: {_list(s.avoid)}

=== RESUME ===
{profile.resume.strip()}

=== JOB ===
Title: {job.title}
Company: {job.company}

{job.description.strip()}

Return only JSON matching the schema."""


def build_repair_prompt(original_prompt: str, bad_reply: str, error: str) -> str:
    return (
        f"{original_prompt}\n\n"
        f"Your previous answer was invalid.\n"
        f"Previous answer:\n{bad_reply[:2000]}\n\n"
        f"Validation error:\n{error}\n\n"
        f"Return a corrected answer as JSON only."
    )


def check_rules(a: FitAssessment, profile: Profile) -> None:
    """Rules the JSON schema alone cannot express."""
    allowed = {m.lower() for m in profile.skills.must_have}
    invented = [m for m in a.missing_must_haves if m.lower() not in allowed]
    if invented:
        raise ValueError(
            f"missing_must_haves must only contain items from the must-have list "
            f"{sorted(profile.skills.must_have)}; these are not on it: {invented}"
        )


def combine(a: FitAssessment, w: Weights) -> FitScore:
    """Weighted sum of the component scores, using the user's weights."""
    components = {
        "skills": a.skills_score,
        "seniority": a.seniority_score,
        "domain": a.domain_score,
        "preferences": a.preferences_score,
    }
    weights = w.model_dump()
    score = round(sum(components[k] * weights[k] for k in components) / 100)
    verdict = "strong" if score >= 75 else "possible" if score >= 50 else "weak"
    return FitScore(score=score, verdict=verdict, components=components, assessment=a)


def score_fit(llm: LLMClient, profile: Profile, job: Job) -> tuple[FitScore, int]:
    """Return (FitScore, number of LLM calls used)."""
    schema = FitAssessment.model_json_schema()
    base_prompt = build_prompt(profile, job)
    prompt = base_prompt
    last_error = "no attempts made"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        reply = llm.generate_json(prompt, schema)
        try:
            assessment = FitAssessment.model_validate_json(reply)
            check_rules(assessment, profile)
            return combine(assessment, profile.weights), attempt
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            prompt = build_repair_prompt(base_prompt, reply, last_error)

    raise ScoringError(f"LLM output invalid after {MAX_ATTEMPTS} attempts: {last_error}")
