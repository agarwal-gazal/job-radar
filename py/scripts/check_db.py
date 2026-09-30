import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Find py/.env relative to THIS file, not to wherever you happen to be
# standing. __file__ is py/scripts/check_db.py, so parent.parent is py/
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

url = os.environ.get("DATABASE_URL")
if not url:
    raise SystemExit(f"DATABASE_URL not set. Looked in: {ENV_PATH}")

with psycopg.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM scored_jobs;")
        print("rows in scored_jobs:", cur.fetchone()[0])

        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
        print("pgvector version:", cur.fetchone()[0])
