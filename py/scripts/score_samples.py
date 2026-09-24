"""Score jobs from a JSON file against a user profile.

Run from the py/ folder:
  python -m scripts.score_samples                       # uses profiles/example
  python -m scripts.score_samples --profile yourname    # uses profiles/yourname
  python -m scripts.score_samples --jobs ../data/sample_jobs.json

Prints a ranked table and writes data/scores-<profile>.json.
"""

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from app.llm import make_llm
from app.models import Job
from app.prefilter import prefilter
from app.profile import load_profile
from app.scorer import ScoringError, score_fit

DATA = Path(__file__).resolve().parents[2] / "data"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score jobs against a profile.")
    parser.add_argument("--profile", default="example")
    parser.add_argument("--jobs", default=str(DATA / "sample_jobs.json"))
    args = parser.parse_args()

    load_dotenv()
    profile = load_profile(args.profile)
    llm = make_llm(profile.llm.provider, profile.llm.model)
    jobs = [Job(**j) for j in json.loads(Path(args.jobs).read_text())]

    results, skipped = [], []
    for job in jobs:
        reason = prefilter(job, profile)
        if reason:
            skipped.append((job, reason))
            continue
        start = time.perf_counter()
        try:
            fit, attempts = score_fit(llm, profile, job)
        except ScoringError as exc:
            print(f"FAILED  {job.company}: {exc}")
            continue
        results.append({
            "company": job.company, "title": job.title, "url": job.url,
            "attempts": attempts, "seconds": round(time.perf_counter() - start, 1),
            **fit.model_dump(),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    print(f"\nProfile: {args.profile} · Model: {llm.model_name}\n")
    print(f"{'Score':>5}  {'Verdict':<8}  {'Company':<24}  Title")
    for r in results:
        a = r["assessment"]
        print(f"{r['score']:>5}  {r['verdict']:<8}  {r['company'][:24]:<24}  {r['title'][:50]}")
        print(f"       parts: {r['components']}")
        print(f"       gaps: {', '.join(a['gaps'][:4]) or '-'}")
    for job, reason in skipped:
        print(f" skip  {job.company[:24]:<24}  {job.title[:40]}  ({reason})")

    out = DATA / f"scores-{args.profile}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nScored {len(results)}, skipped {len(skipped)} without an LLM call. Saved to {out.name}")


if __name__ == "__main__":
    main()
