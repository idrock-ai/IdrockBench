-- ============================================================
-- idrock eval — model submission table
-- Run this once in the Supabase SQL editor (Dashboard -> SQL).
-- ============================================================

create table if not exists public.model_submissions (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    name        text not null check (char_length(name) between 1 and 120),
    email       text not null check (char_length(email) between 3 and 160),
    model_name  text not null check (char_length(model_name) between 1 and 120),
    company     text check (char_length(company) <= 120),
    notes       text check (char_length(notes) <= 1500),
    -- Consent is recorded, not assumed. Without a timestamp there is no record
    -- that the person agreed, which is the whole basis for holding the data.
    consent_at  timestamptz not null default now(),
    -- Hashed, never the raw address: enough to rate-limit, not enough to track.
    ip_hash     text
);

-- Rate limiting for the edge function: one lookup, no extra table.
create index if not exists model_submissions_ip_recent
    on public.model_submissions (ip_hash, created_at desc);

-- Row Level Security: enable it with NO policies, which blocks all access from
-- the public anon key. The submit-model Edge Function writes rows using the
-- service_role key, which bypasses RLS — so the table is never publicly
-- writable or readable. Review submissions in the Supabase Table editor.
alter table public.model_submissions enable row level security;
