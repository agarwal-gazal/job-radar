#!/usr/bin/env python3
"""Label jobs as good/bad fit to build an eval golden set.

Usage:
    python scripts/label_jobs.py --jobs data/samples.jsonl --n 50
"""
import argparse, json, random, sys
from datetime import datetime
from pathlib import Path

OUT = Path("py/evals/golden.jsonl")


def load_jobs(path: Path) -> list[dict]:
    """Read either JSONL (one object per line) or a plain JSON array."""
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("["):
        return json.loads(text)
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def already_labelled() -> set:
    if not OUT.exists():
        return set()
    return {json.loads(l)["job_id"] for l in OUT.read_text().splitlines() if l.strip()}


def stratify(jobs: list[dict], n: int) -> list[dict]:
    """Sample across the score range, not just the top.

    TODO: split jobs into buckets by job.get("score"):
          80-100, 50-79, below 50, and prefiltered/no score.
    TODO: take roughly 15 / 15 / 10 / 10 of them, random.sample
          within each bucket, and return the combined list.
    For now: a plain random sample so the script runs.
    """
    random.seed(29)
    return random.sample(jobs, min(n, len(jobs)))


def show(job: dict) -> None:
    """Print the job WITHOUT its score, so you label blind."""
    print("\n" + "=" * 70)
    print(f"{job.get('title', '?')}  @  {job.get('company', '?')}")
    print(f"{job.get('location', '?')}")
    print("-" * 70)
    desc = (job.get("description") or "")[:1200]
    print(desc)
    print("=" * 70)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True, type=Path)
    ap.add_argument("--n", type=int, default=50)
    args = ap.parse_args()

    jobs = load_jobs(args.jobs)
    done = already_labelled()
    queue = [j for j in stratify(jobs, args.n) if j.get("id") not in done]
    print(f"{len(done)} already labelled · {len(queue)} to go")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("a", encoding="utf-8") as f:
        for i, job in enumerate(queue, 1):
            show(job)
            print(f"[{i}/{len(queue)}]  y = would apply · n = would not "
                  "· m = maybe · s = skip · q = save and quit")
            choice = input("> ").strip().lower()

            if choice == "q":
                break
            if choice == "s" or choice not in {"y", "n", "m"}:
                continue

            note = input("why? (one line, enter to skip) ").strip()

            # TODO: build the record. Include job_id, title, company,
            #       label ("yes"/"no"/"maybe"), note, labelled_at,
            #       and a "system" dict with whatever scores the job
            #       already carries, so tomorrow can compare.
            record = {}

            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()   # write to disk now, so a crash loses nothing

    print(f"\nSaved to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
