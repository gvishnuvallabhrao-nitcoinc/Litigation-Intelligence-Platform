-- ============================================================
-- Legal Intelligence Platform — Supabase Schema
-- Run in order: extensions → tables → indexes → RLS
-- ============================================================

-- pgvector: stores InLegalBERT 768-dim embeddings for similarity search
create extension if not exists vector;

-- ============================================================
-- 1. CASES
-- ============================================================

create table if not exists cases (
    id               bigserial primary key,
    case_id          text        not null unique,          -- e.g. "ik_123456"
    court            text        not null,
    judge_name       text        not null,                 -- normalized snake_case key
    case_type        text        not null                  -- IPR / civil / criminal / labour / tax / constitutional
                         check (case_type in ('IPR','civil','criminal','labour','tax','constitutional','unknown')),
    petitioner_type  text        not null default 'unknown'
                         check (petitioner_type in ('individual','corporation','government','NGO','unknown')),
    respondent_type  text        not null default 'unknown'
                         check (respondent_type in ('individual','corporation','government','NGO','unknown')),
    acts_cited       text[]      not null default '{}',    -- ["TM Act 29", "Copyright Act 51"]
    hearing_count    integer     not null default 0,
    judgment_date    date,
    outcome          text        not null default 'unknown'
                         check (outcome in ('allowed','dismissed','partially_allowed','unknown')),
    indian_kanoon_url text,
    judgment_text    text        not null default '',
    summary          text        generated always as (left(judgment_text, 300)) stored,
    embedding        vector(768),                          -- InLegalBERT CLS token
    created_at       timestamptz not null default now(),
    updated_at       timestamptz not null default now()
);

-- fast lookups used by API filters
create index if not exists cases_court_idx         on cases (court);
create index if not exists cases_judge_name_idx    on cases (judge_name);
create index if not exists cases_case_type_idx     on cases (case_type);
create index if not exists cases_outcome_idx       on cases (outcome);
create index if not exists cases_judgment_date_idx on cases (judgment_date desc);
create index if not exists cases_acts_cited_idx    on cases using gin (acts_cited);

-- HNSW index for fast approximate nearest-neighbour search on embeddings
-- inner product = cosine similarity when vectors are L2-normalised (which embedder.py does)
create index if not exists cases_embedding_idx
    on cases using hnsw (embedding vector_ip_ops)
    with (m = 16, ef_construction = 64);

-- ============================================================
-- 2. JUDGE STATS  (precomputed nightly)
-- ============================================================

create table if not exists judge_stats (
    id                      bigserial primary key,
    judge_name              text    not null,
    case_type               text    not null default 'all',  -- 'all' = across all types
    total_cases             integer not null default 0,
    allowed                 integer not null default 0,
    dismissed               integer not null default 0,
    partially_allowed       integer not null default 0,
    avg_hearing_count       numeric(5,2) not null default 0,
    allow_rate              numeric(5,4) generated always as (
                                case when total_cases = 0 then 0
                                else allowed::numeric / total_cases end
                            ) stored,
    last_updated            timestamptz not null default now(),

    unique (judge_name, case_type)
);

create index if not exists judge_stats_judge_name_idx on judge_stats (judge_name);
create index if not exists judge_stats_case_type_idx  on judge_stats (case_type);

-- ============================================================
-- 3. FIRMS  (multi-tenant — one row per law firm / client)
-- ============================================================

create table if not exists firms (
    id         uuid        primary key default gen_random_uuid(),
    name       text        not null,
    email      text        not null unique,
    plan       text        not null default 'phase1'
                   check (plan in ('phase1','phase1_phase2','trial')),
    created_at timestamptz not null default now()
);

-- ============================================================
-- 4. SAVED SEARCHES  (powers the /history route)
-- ============================================================

create table if not exists saved_searches (
    id            bigserial   primary key,
    firm_id       uuid        not null references firms (id) on delete cascade,
    query_text    text        not null,
    filters       jsonb       not null default '{}',  -- {"case_type": "IPR", "court": "Delhi HC"}
    result_ids    text[]      not null default '{}',  -- case_id list from that search
    created_at    timestamptz not null default now()
);

create index if not exists saved_searches_firm_idx on saved_searches (firm_id);
create index if not exists saved_searches_created_at_idx on saved_searches (created_at desc);

-- ============================================================
-- 5. AUTO-UPDATE updated_at on cases
-- ============================================================

create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create or replace trigger cases_set_updated_at
    before update on cases
    for each row execute function set_updated_at();

-- ============================================================
-- 6. ROW-LEVEL SECURITY
-- ============================================================

-- cases and judge_stats are read-only for authenticated users
alter table cases        enable row level security;
alter table judge_stats  enable row level security;
alter table firms        enable row level security;
alter table saved_searches enable row level security;

-- Public read on cases (judgments are public domain)
create policy "cases_public_read"
    on cases for select
    using (true);

-- Public read on judge stats
create policy "judge_stats_public_read"
    on judge_stats for select
    using (true);

-- Firms: each firm sees only itself
create policy "firms_self_read"
    on firms for select
    using (id = (current_setting('app.firm_id', true))::uuid);

-- Saved searches: each firm sees only its own
create policy "saved_searches_own_firm"
    on saved_searches for all
    using (firm_id = (current_setting('app.firm_id', true))::uuid);

-- ============================================================
-- 7. HELPER VIEW — recent judgments per judge (used by API)
-- ============================================================

create or replace view judge_recent_cases as
select
    judge_name,
    case_id,
    case_type,
    outcome,
    judgment_date,
    indian_kanoon_url,
    summary,
    row_number() over (partition by judge_name order by judgment_date desc) as rn
from cases
where outcome != 'unknown';

-- ============================================================
-- 8. SIMILARITY SEARCH FUNCTION  (called from FastAPI)
-- ============================================================

create or replace function match_cases(
    query_embedding  vector(768),
    match_count      int     default 10,
    filter_court     text    default null,
    filter_case_type text    default null,
    filter_outcome   text    default null
)
returns table (
    case_id          text,
    court            text,
    judge_name       text,
    case_type        text,
    outcome          text,
    judgment_date    date,
    acts_cited       text[],
    summary          text,
    indian_kanoon_url text,
    similarity       float
)
language sql stable as $$
    select
        c.case_id,
        c.court,
        c.judge_name,
        c.case_type,
        c.outcome,
        c.judgment_date,
        c.acts_cited,
        c.summary,
        c.indian_kanoon_url,
        (c.embedding <#> query_embedding) * -1 as similarity   -- inner product, higher = more similar
    from cases c
    where c.embedding is not null
      and (filter_court     is null or c.court     = filter_court)
      and (filter_case_type is null or c.case_type = filter_case_type)
      and (filter_outcome   is null or c.outcome   = filter_outcome)
    order by c.embedding <#> query_embedding
    limit match_count;
$$;
