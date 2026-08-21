create table if not exists public.model_submissions (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    name        text not null check (char_length(name) between 1 and 120),
    email       text not null check (char_length(email) between 3 and 160),
    model_name  text not null check (char_length(model_name) between 1 and 120),
    company     text check (char_length(company) <= 120),
    notes       text check (char_length(notes) <= 1500),
    consent_at  timestamptz not null default now(),
    ip_hash     text
);

create index if not exists model_submissions_ip_recent
    on public.model_submissions (ip_hash, created_at desc);

alter table public.model_submissions enable row level security;
