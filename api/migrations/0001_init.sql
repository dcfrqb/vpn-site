-- Stage 3: accounts, sessions, passkeys, one-time tokens, outbox, audit.

create table web.accounts (
    id uuid primary key default gen_random_uuid(),
    email text,
    email_verified_at timestamptz,
    password_hash text,
    telegram_id bigint unique,
    telegram_username text,
    telegram_first_name text,
    created_at timestamptz not null default now(),
    last_login_at timestamptz,
    is_admin boolean not null default false
);

-- Case-insensitive unique email: citext if the extension is available, lower() index otherwise.
-- The app stores emails lowercased either way.
do $$
begin
    begin
        create extension if not exists citext;
    exception when others then
        raise notice 'citext unavailable, using lower(email) index';
    end;
    if exists (select 1 from pg_extension where extname = 'citext') then
        alter table web.accounts alter column email type citext;
        create unique index accounts_email_key on web.accounts (email);
    else
        create unique index accounts_email_key on web.accounts (lower(email));
    end if;
end $$;

create table web.sessions (
    id_hash bytea primary key,
    account_id uuid not null references web.accounts (id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    last_seen_at timestamptz not null default now(),
    ip inet,
    user_agent text,
    revoked_at timestamptz
);
create index sessions_account_idx on web.sessions (account_id);

create table web.webauthn_credentials (
    id bytea primary key,
    account_id uuid not null references web.accounts (id) on delete cascade,
    public_key bytea not null,
    sign_count bigint not null default 0,
    transports text[] not null default '{}',
    name text not null,
    created_at timestamptz not null default now(),
    last_used_at timestamptz
);
create index webauthn_credentials_account_idx on web.webauthn_credentials (account_id);

create table web.webauthn_challenges (
    id uuid primary key default gen_random_uuid(),
    challenge bytea not null,
    account_id uuid references web.accounts (id) on delete cascade,
    kind text not null check (kind in ('register', 'login')),
    expires_at timestamptz not null
);

create table web.auth_tokens (
    token_hash bytea primary key,
    account_id uuid not null references web.accounts (id) on delete cascade,
    kind text not null check (kind in ('verify_email', 'reset_password')),
    email text not null, -- the address the token was issued for
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    used_at timestamptz
);
create index auth_tokens_account_idx on web.auth_tokens (account_id);

create table web.outbox (
    id bigserial primary key,
    to_email text not null,
    subject text not null,
    body text not null,
    created_at timestamptz not null default now(),
    sent_at timestamptz
);

create table web.audit_log (
    id bigserial primary key,
    account_id uuid references web.accounts (id) on delete set null,
    event text not null,
    ip inet,
    user_agent text,
    meta jsonb not null default '{}',
    created_at timestamptz not null default now()
);
create index audit_log_account_idx on web.audit_log (account_id, created_at);
