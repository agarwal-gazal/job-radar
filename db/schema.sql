-- pgvector gives Postgres the `vector` column type.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS scored_jobs (
    id              bigserial PRIMARY KEY,

    -- where it came from
    source          text        NOT NULL,       -- 'lever' | 'greenhouse' | 'ashby'
    external_id     text        NOT NULL,       -- the board's own id for this job
    url             text        NOT NULL,
    content_hash    text        NOT NULL,       -- sha256 of title+company+description

    -- the job itself
    title           text        NOT NULL,
    company         text        NOT NULL,
    location        text,
    is_remote       boolean,
    description     text,
    posted_at       timestamptz,

    -- the scoring result, one row per job per profile
    profile_name    text        NOT NULL,       -- profiles/<name>/profile.toml
    total_score     integer     NOT NULL,       -- 0-100, the weighted sum
    skills_score        integer,
    seniority_score     integer,
    domain_score        integer,
    preferences_score   integer,
    matched_skills      jsonb   NOT NULL DEFAULT '[]'::jsonb,
    missing_must_haves  jsonb   NOT NULL DEFAULT '[]'::jsonb,
    gaps            text,
    reasons         text,

    -- provenance: which model produced this, and when
    model           text,
    prefiltered     boolean     NOT NULL DEFAULT false,  -- true = rejected before any LLM call
    scored_at       timestamptz NOT NULL DEFAULT now(),

    -- filled in later, once embeddings exist. 1536 is indexable; 3072 is not.
    embedding       vector(1536),

    -- the same job scored for the same profile only ever has one row
    CONSTRAINT scored_jobs_unique UNIQUE (source, external_id, profile_name)
);

-- the query you will actually run: my best matches, newest first
CREATE INDEX IF NOT EXISTS scored_jobs_profile_score_idx
    ON scored_jobs (profile_name, total_score DESC, posted_at DESC);

-- skip anything already scored, without reading the whole table
CREATE INDEX IF NOT EXISTS scored_jobs_hash_idx
    ON scored_jobs (content_hash);
