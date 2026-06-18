-- ============================================================
-- LindaAI — Relational Schema (Document 5 of 6)
-- PostgreSQL / Supabase compatible DDL
-- Design goals: integrity, RLS, and LEAN storage (free tier 500 MB).
--   * compact scan results stored as JSONB (no PDF blobs, ever)
--   * raw logs pruned after report generation
--   * enums instead of wide text columns
-- ============================================================

-- ---------- Extensions ----------
create extension if not exists "pgcrypto";   -- gen_random_uuid()

-- ---------- Enumerated types (cheap, self-documenting) ----------
create type domain_status   as enum ('pending', 'verified', 'revoked');
create type scan_status     as enum ('queued', 'running', 'complete', 'failed');
create type severity_level  as enum ('critical', 'high', 'medium', 'low');
create type payment_status  as enum ('initiated', 'paid', 'failed', 'cancelled');
create type report_lang     as enum ('en', 'sw');

-- ============================================================
-- 1. organizations  (one per owner in MVP; structured for growth)
-- ============================================================
create table organizations (
    id          uuid primary key default gen_random_uuid(),
    name        text not null check (char_length(name) between 1 and 120),
    created_at  timestamptz not null default now()
);

-- ============================================================
-- 2. users  (profile mirror of Supabase auth.users)
--    auth.users holds credentials; we keep a thin profile + org link.
-- ============================================================
create table users (
    id          uuid primary key references auth.users (id) on delete cascade,
    org_id      uuid not null references organizations (id) on delete cascade,
    email       text not null,
    full_name   text check (char_length(full_name) <= 120),
    locale      report_lang not null default 'en',
    created_at  timestamptz not null default now(),
    unique (email)
);
create index idx_users_org on users (org_id);

-- ============================================================
-- 3. verified_domains  (the ownership gate — scans require a row here)
-- ============================================================
create table verified_domains (
    id              uuid primary key default gen_random_uuid(),
    org_id          uuid not null references organizations (id) on delete cascade,
    hostname        text not null
                    check (hostname ~ '^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$'),
    verify_token    text not null default ('linda-verify=' || encode(gen_random_bytes(16), 'hex')),
    status          domain_status not null default 'pending',
    created_at      timestamptz not null default now(),
    verified_at     timestamptz,
    -- a hostname can only be claimed once across the platform (prevents
    -- two orgs both "owning" the same domain)
    unique (hostname),
    -- integrity: verified rows must carry a timestamp
    check (status <> 'verified' or verified_at is not null)
);
create index idx_domains_org on verified_domains (org_id);
create index idx_domains_status on verified_domains (status);

-- ============================================================
-- 4. scans  (one per run; stores compact findings as JSONB)
--    raw_findings example:
--      [{"id":"missing-dmarc","severity":"high","category":"dns","detail":null}, ...]
-- ============================================================
create table scans (
    id              uuid primary key default gen_random_uuid(),
    domain_id       uuid not null references verified_domains (id) on delete cascade,
    org_id          uuid not null references organizations (id) on delete cascade,
    status          scan_status not null default 'queued',
    raw_findings    jsonb not null default '[]'::jsonb,
    overall_risk    severity_level,                 -- null until summarized
    fail_reason     text,
    -- KPI / cost telemetry (the PRD success metric lives here)
    llm_prompt_tokens      integer not null default 0,
    llm_completion_tokens  integer not null default 0,
    cost_kes               numeric(8,4) not null default 0,  -- e.g. 0.0150
    started_at      timestamptz,
    completed_at    timestamptz,
    created_at      timestamptz not null default now(),
    check (jsonb_typeof(raw_findings) = 'array'),
    check (status <> 'failed' or fail_reason is not null)
);
create index idx_scans_org on scans (org_id);
create index idx_scans_domain on scans (domain_id);
create index idx_scans_created on scans (created_at desc);

-- ============================================================
-- 5. vulnerability_summaries  (denormalized severity rollup per scan)
--    Powers the dashboard grid without re-aggregating JSONB each load.
--    One row per scan; counts only -> tiny footprint.
-- ============================================================
create table vulnerability_summaries (
    scan_id         uuid primary key references scans (id) on delete cascade,
    org_id          uuid not null references organizations (id) on delete cascade,
    critical_count  smallint not null default 0 check (critical_count >= 0),
    high_count      smallint not null default 0 check (high_count >= 0),
    medium_count    smallint not null default 0 check (medium_count >= 0),
    low_count       smallint not null default 0 check (low_count >= 0),
    top_priority_id text,                  -- e.g. 'cert-expiring-soon'
    summary_en      text,                  -- LLM exec summary (English)
    summary_sw      text,                  -- LLM exec summary (Kiswahili)
    created_at      timestamptz not null default now()
);
create index idx_vulnsum_org on vulnerability_summaries (org_id);

-- ============================================================
-- 6. payments  (Daraja / M-Pesa pay-as-you-go; unlocks a report)
-- ============================================================
create table payments (
    id                 uuid primary key default gen_random_uuid(),
    scan_id            uuid not null references scans (id) on delete cascade,
    org_id             uuid not null references organizations (id) on delete cascade,
    amount_kes         numeric(10,2) not null check (amount_kes >= 0),
    status             payment_status not null default 'initiated',
    -- Daraja reconciliation fields
    merchant_request_id  text,
    checkout_request_id  text,
    mpesa_receipt        text unique,      -- set on success; unique guards replays
    phone_e164           text check (phone_e164 ~ '^\+?254[17][0-9]{8}$'),
    created_at         timestamptz not null default now(),
    paid_at            timestamptz,
    check (status <> 'paid' or mpesa_receipt is not null)
);
create index idx_payments_scan on payments (scan_id);
create index idx_payments_org on payments (org_id);

-- ============================================================
-- Row-Level Security  (every table: a user sees only their org's rows)
-- ============================================================
alter table organizations          enable row level security;
alter table users                  enable row level security;
alter table verified_domains       enable row level security;
alter table scans                  enable row level security;
alter table vulnerability_summaries enable row level security;
alter table payments               enable row level security;

-- helper: the set of org_ids the current auth user belongs to
create or replace function auth_org_ids() returns setof uuid
language sql stable security definer set search_path = public as $$
    select org_id from users where id = auth.uid()
$$;

-- read/write own org only (service role bypasses RLS for backend writes)
create policy org_self      on organizations
    for select using (id in (select auth_org_ids()));

create policy users_self     on users
    for select using (org_id in (select auth_org_ids()));

create policy domains_self   on verified_domains
    for all using (org_id in (select auth_org_ids()))
    with check (org_id in (select auth_org_ids()));

create policy scans_self     on scans
    for select using (org_id in (select auth_org_ids()));

create policy vulnsum_self   on vulnerability_summaries
    for select using (org_id in (select auth_org_ids()));

create policy payments_self  on payments
    for select using (org_id in (select auth_org_ids()));

-- ============================================================
-- Storage hygiene (stay under free-tier 500 MB)
-- Run nightly via Supabase scheduled function:
--   * blank raw_findings older than 90 days (summaries are retained)
-- ============================================================
-- update scans set raw_findings = '[]'::jsonb
--   where created_at < now() - interval '90 days'
--     and raw_findings <> '[]'::jsonb;
