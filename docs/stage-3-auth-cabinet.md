# Stage 3: auth and cabinet

Scope: sign-in with Telegram, email + password, passkey; account settings; cabinet on mock bot data.
Out of scope here: payments (needs YooKassa test shop keys), admin (stage 4), real bot data (after bot 3.0).

## Architecture

- Same origin: nginx serves web at `/` and api at `/api/` on `vpn.crs-projects.com`. Browser calls `/api/...` directly with cookies.
- Next.js server components call the api at `API_INTERNAL_URL` and forward the incoming `cookie` header.
- The api owns all auth. The web never sees password hashes or session ids beyond the cookie it forwards.
- Storage: the site's own Postgres, schema `web`. SQL migrations in `api/migrations/NNNN_name.sql`, applied at api startup by a tiny runner (`web.schema_migrations`). Driver: asyncpg, no ORM.

## Data model (schema `web`)

- `accounts`: id uuid pk, email citext unique null, email_verified_at, password_hash null, telegram_id bigint unique null, telegram_username, telegram_first_name, created_at, last_login_at, is_admin bool default false.
- `sessions`: id_hash bytea pk (sha256 of the token), account_id fk, created_at, expires_at, last_seen_at, ip inet, user_agent text, revoked_at.
- `webauthn_credentials`: id bytea pk (credential id), account_id fk, public_key bytea, sign_count bigint, transports text[], name text, created_at, last_used_at.
- `webauthn_challenges`: id uuid pk, challenge bytea, account_id null, kind (register|login), expires_at. One use.
- `auth_tokens`: token_hash bytea pk, account_id fk, kind (verify_email|reset_password), expires_at, used_at.
- `outbox`: id, to_email, subject, body, created_at, sent_at. Mail goes here; SMTP sender is optional (env `SMTP_*`); without SMTP it only logs.
- `audit_log`: id, account_id null, event text, ip, user_agent, meta jsonb, created_at.

## Security rules

- Passwords: argon2id (argon2-cffi defaults), min length 10, max 128, reject if equal to email.
- Session: 32-byte random token, cookie `__Host-sid` (Secure, HttpOnly, SameSite=Lax, Path=/), 30 days, sliding `last_seen_at`; DB stores only sha256. Cookie name configurable (`SESSION_COOKIE`) for local http dev.
- New session id on every login; logout revokes it; "sign out everywhere" revokes all.
- CSRF: every non-GET `/api/*` request must carry `Origin` equal to `PUBLIC_ORIGIN` (403 otherwise). SameSite=Lax as second layer.
- Rate limits (in-process, per IP and per account/email): login 10/15min, register 5/hour, forgot 3/hour, passkey 20/15min. 429 with `retry_after`. nginx `limit_req` on `/api/auth/` as outer layer.
- Uniform errors: login failure never says whether the email exists; forgot always answers 200.
- Telegram Login Widget: verify HMAC-SHA256 with `sha256(BOT_TOKEN)` as key over sorted `key=value` lines without `hash`; reject `auth_date` older than 24h.
- WebAuthn (py_webauthn): RP ID `WEBAUTHN_RP_ID`, origin `PUBLIC_ORIGIN`, user verification preferred, discoverable credentials (resident key required) so login works without typing email.
- Audit every login, failed login, logout, password change, passkey add/remove, telegram link/unlink.
- No stack traces or internals in responses.

## API contract

All JSON. Errors: `{"error": "<code>", "message": "<russian text for the user>"}`.

Auth:
- `POST /api/auth/register` `{email, password}` → 201 `{account}` + session cookie. Sends verify email to outbox.
- `POST /api/auth/login` `{email, password}` → 200 `{account}` + cookie. 401 `invalid_credentials`.
- `POST /api/auth/logout` → 204.
- `POST /api/auth/logout-all` → 204.
- `POST /api/auth/telegram` `{id, first_name, last_name?, username?, photo_url?, auth_date, hash}` → 200 `{account}` + cookie. Creates the account if the telegram id is new. If a session exists, links telegram to the current account instead (409 `telegram_taken` if linked elsewhere).
- `POST /api/auth/forgot` `{email}` → 200 always.
- `POST /api/auth/reset` `{token, password}` → 204, revokes all sessions.
- `POST /api/auth/verify-email` `{token}` → 204.
- `POST /api/auth/passkey/login/options` → 200 PublicKeyCredentialRequestOptions JSON + `challenge_id`.
- `POST /api/auth/passkey/login/verify` `{challenge_id, credential}` → 200 `{account}` + cookie.

Me (session required, else 401 `unauthorized`):
- `GET /api/me` → `{account}` where account = `{id, email, email_verified, telegram: {id, username, first_name} | null, has_password, passkeys: [{id, name, created_at, last_used_at}], created_at}`.
- `POST /api/me/password` `{current_password?, new_password}` → 204 (current required if a password exists).
- `POST /api/me/email` `{email, password?}` → 204, marks unverified, sends verify mail.
- `DELETE /api/me/telegram` → 204 (409 `last_login_method` if it would leave no way to sign in).
- `POST /api/me/passkeys/options` → registration options JSON + `challenge_id`.
- `POST /api/me/passkeys/verify` `{challenge_id, credential, name?}` → 201 passkey.
- `DELETE /api/me/passkeys/{id}` → 204 (409 `last_login_method` guard).
- `GET /api/me/sessions` → `[{id, current, created_at, last_seen_at, ip, user_agent}]` (id = short public id, not the token).
- `DELETE /api/me/sessions/{id}` → 204.

Cabinet (session required; data from the bot gateway by `telegram_id`):
- `GET /api/cabinet` → `{linked: bool, subscription: {plan, status, valid_until, days_left, device_limit, sub_url, traffic_month_gb} | null, devices: [{name, last_seen_at}], payments: [{date, plan, months, amount_rub, status}], nodes: [{name, country, online, ping_ms}], demo: true}`. Without telegram: `linked:false`, other fields empty. The mock returns deterministic demo data per telegram id and always sets `demo: true`.

## Frontend

Pages (mobile 390px and desktop 1280px both required):
- `/login`: three methods on one screen: Telegram widget (`@crs_vpn_bot`), email + password form, "войти по паскею" button. Link to `/register` and `/forgot`.
- `/register`: email + password (+ repeat), consent checkbox for the personal data policy (required).
- `/forgot`, `/reset?token=`, `/verify?token=`.
- `/cabinet`: display-style screen from the mockup (days left, traffic bars, nodes), subscription link with copy, devices, payments. `demo` badge "пример" while data is mock. Empty state without telegram: explain and offer "привязать telegram" and "выбрать тариф".
- `/cabinet/settings`: email and password, telegram link/unlink (widget), passkeys list + "добавить паскей", active sessions with revoke, "выйти везде".
- Header on inner pages: compact nav with brand, "кабинет", "выйти".
- Auth guard: `/cabinet*` server-side calls `/api/me`; 401 → redirect `/login?next=...`. `/login` with a valid session → redirect `/cabinet`.
- Passkeys in the browser via `@simplewebauthn/browser`.
- Style: existing tokens in `web/app/globals.css`, Teenage Engineering principles, one accent `#f05a24`, no yellow, thin Onest + JetBrains Mono. Forms: hairline inputs, pill buttons, error text in plain words.

## Config (env)

`PUBLIC_ORIGIN`, `SESSION_COOKIE` (default `__Host-sid`), `TELEGRAM_LOGIN_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `SMTP_HOST/PORT/USER/PASSWORD/FROM` (optional).

## Manual steps for the owner

- BotFather → `/setdomain` for `@crs_vpn_bot` → `vpn.crs-projects.com` (Telegram widget works only on the bot's domain).
- SMTP account for real emails (until then letters sit in `web.outbox`).
