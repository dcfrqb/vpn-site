-- Sign-in through the Telegram app: the site creates a request, the login bot confirms it.
create table web.tg_login_requests (
    id uuid primary key default gen_random_uuid(),
    start_hash bytea not null unique,        -- sha256 of the /start payload
    browser_hash bytea not null,             -- sha256 of the cookie held by the browser that started it
    mode text not null check (mode in ('login', 'link')),
    account_id uuid references web.accounts (id) on delete cascade,  -- link mode: who links
    status text not null default 'pending'
        check (status in ('pending', 'claimed', 'confirmed', 'denied', 'consumed')),
    telegram_id bigint,
    telegram_username text,
    telegram_first_name text,
    ip inet,
    user_agent text,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null
);
create index tg_login_requests_expires_idx on web.tg_login_requests (expires_at);
