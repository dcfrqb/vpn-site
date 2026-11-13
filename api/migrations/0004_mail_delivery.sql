-- Durable SMTP retry queue. No addresses, bodies or token values are logged.
alter table web.outbox
    add column delivery_key uuid not null default gen_random_uuid(),
    add column attempts integer not null default 0,
    add column next_attempt_at timestamptz not null default now(),
    add column lease_until timestamptz,
    add column lease_token uuid,
    add column last_error text,
    add column discarded_at timestamptz,
    add column token_hash bytea;
create index outbox_due_idx on web.outbox (next_attempt_at)
    where sent_at is null and discarded_at is null;
