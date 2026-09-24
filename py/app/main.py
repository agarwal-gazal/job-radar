"""HTTP API for the scoring service.

Run locally:  uvicorn app.main:app --reload
Docs:         http://127.0.0.1:8000/docs
"""

from functools import lru_cache

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from .llm import make_llm
from .models import ScoreRequest, ScoreResponse
from .prefilter import prefilter
from .profile import PROFILES_DIR, Profile, ProfileError, load_profile
from .scorer import ScoringError, score_fit

load_dotenv()

app = FastAPI(title="Job Radar — scoring service", version="0.2.0")


@lru_cache
def get_profile(name: str) -> Profile:
    return load_profile(name)


@lru_cache
def get_llm(provider: str, model: str | None):
    return make_llm(provider, model)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/profiles")
def list_profiles() -> list[str]:
    return sorted(p.parent.name for p in PROFILES_DIR.glob("*/profile.toml"))


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    try:
        profile = get_profile(req.profile)
    except ProfileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    reason = prefilter(req.job, profile)
    if reason:
        return ScoreResponse(job=req.job, profile=req.profile, skipped=reason)

    llm = get_llm(profile.llm.provider, profile.llm.model)
    try:
        fit, attempts = score_fit(llm, profile, req.job)
    except ScoringError as exc:
        # 502: the upstream model failed us, not the caller.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ScoreResponse(job=req.job, profile=req.profile, fit=fit, model=llm.model_name, attempts=attempts)
