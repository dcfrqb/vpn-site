create table web.google_identities (
    subject text primary key,
    account_id uuid not null unique references web.accounts(id) on delete cascade,
    email text not null,
    created_at timestamptz not null default now()
);
create table web.google_challenges (
    nonce_hash bytea primary key,
    account_id uuid references web.accounts(id) on delete cascade,
    expires_at timestamptz not null
);
