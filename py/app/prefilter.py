"""Cheap rule-based checks that run before the LLM.

Why: LLM calls cost money and time. Jobs that obviously don't fit a user's
hard rules (a deal-breaker keyword, an onsite-only role for a remote-only
user, a stack they want to avoid in the title) are skipped for free.
In an interview this is "filter cheaply first, spend the expensive model
only on candidates that survive".
"""

import re

from .models import Job
from .profile import Profile

ONSITE_PATTERNS = [r"\bonsite only\b", r"\bon-site only\b", r"\bwork from office\b", r"\bno remote\b"]


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase.lower())}(?!\w)", text) is not None


def prefilter(job: Job, profile: Profile) -> str | None:
    """Return a reason to skip this job, or None if it should be scored."""
    text = f"{job.title}\n{job.description}".lower()
    title = job.title.lower()

    for phrase in profile.deal_breakers.keywords:
        if _contains(text, phrase):
            return f"deal-breaker keyword: '{phrase}'"

    for stack in profile.skills.avoid:
        if _contains(title, stack):
            return f"title mentions a stack you avoid: '{stack}'"

    if profile.preferences.remote_only:
        for pattern in ONSITE_PATTERNS:
            if re.search(pattern, text):
                return "onsite role, but profile is remote-only"

    return None
