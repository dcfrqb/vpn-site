# Stage 3: auth and cabinet

Scope: sign-in with Telegram, email + password, passkey; account settings; cabinet on mock bot data.
Out of scope here: payments (needs YooKassa test shop keys), admin (stage 4). Real data: bot profile + Remnawave panel when `BOT_API_URL` and `REMNAWAVE_API_URL` are set (`docs/cabinet-data.md`).

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
- `POST /api/auth/email/check` `{email}` → `{exists, has_password}` (rate limit 20/15min per IP).
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

Cabinet (session required; data by the account's `telegram_id`, never by a client-supplied id). Where the data comes from: `docs/cabinet-data.md`.
- `GET /api/cabinet` → `{linked: bool, demo: bool, data: Cabinet | null}`.
  - `data` shape (same as `Servers/docs/САЙТ_2026-09-23/bot-site-cabinet-api-spec.md`): `generated_at, partial, errors[], user, subscriptions[], devices[], traffic_daily[30], traffic_by_node[], payments[] (newest first), stats, nodes[]`.
  - `subscriptions[]`: `kind (main|obhod), plan_code, plan_title, legacy, status (active|expired|disabled|limited|unknown), valid_until, is_lifetime, days_left, device_limit, sub_url, traffic {used_bytes, limit_bytes, reset (month|day|week|none), month_used_bytes}, package, online_at, last_node`. Lifetime = panel `expireAt` year >= 2099: `valid_until` and `days_left` null.
  - `devices[]`: `subscription, hwid, platform, os_version, model, app, first_seen_at, last_seen_at` (never the device IP).
  - No telegram on the account: `{linked: false, data: null}`.
  - Bot answers 404 (it does not know this telegram id): `{linked: true, data: null}`, the page shows "в боте пока нет подписки".
  - Bot unreachable, timeout (3 s), 5xx or unparseable: 503 `bot_unavailable` (ownership comes from the bot, nothing is shown without it).
  - Panel unreachable (4 s) or broken: 200 with `partial: true, errors: ["panel"]`; subscriptions keep bot fields with `status: "unknown"`, live fields null or empty.
  - `demo: true` while the mock gateway is in use (`BOT_API_URL` or `REMNAWAVE_API_URL` empty). The mock returns deterministic demo data per telegram id in the same shape.
- `DELETE /api/cabinet/devices/{hwid}` (hwid url-encoded) → 204 only if the hwid is in the device list of one of this user's panel accounts (from the bot profile), then the panel deletes it. 404 `device_not_found` otherwise (also without telegram). 503 `bot_unavailable` if the bot or the panel fails. Audit event `device_delete`, `meta = {hwid: <first 6 chars>, ok}`.
- Plans and the public `/api/network` block still come from the static catalog in the mock.

## Frontend

Pages (mobile 390px and desktop 1280px both required):
- `/login`: three methods on one screen: Telegram widget (`@crs_vpn_bot`), email + password form, "войти по паскею" button. Link to `/register` and `/forgot`.
- `/register` redirects to `/login`. The email block on `/login` is one form: email → `POST /api/auth/email/check` → password (existing account) or new password + repeat + consent (new account).
- `/forgot`, `/reset?token=`, `/verify?token=`.
- `/cabinet`: one dark display block per subscription (main, "ru-вход" for obhod): plan, status, days left, valid until, device slots. Traffic: this month per subscription (obhod against its limit), 30-day daily chart (inline SVG, stacked), traffic by node. Subscription links: masked, "показать", copy, QR (client-side, `qrcode`), app hint. Devices with delete (in-page confirm, optimistic). Payments newest first with totals from `stats`. Node grid. States: `linked:false` → link telegram / choose plan; `data:null` → "в боте пока нет подписки"; `demo` → badge "пример"; `partial` → quiet note; 503 → "бот не отвечает".
- `/cabinet/settings`: email and password, telegram link/unlink (widget), passkeys list + "добавить паскей", active sessions with revoke, "выйти везде".
- Header on inner pages: compact nav with brand, "кабинет", "выйти".
- Auth guard: `/cabinet*` server-side calls `/api/me`; 401 → redirect `/login?next=...`. `/login` with a valid session → redirect `/cabinet`.
- Passkeys in the browser via `@simplewebauthn/browser`.
- Style: existing tokens in `web/app/globals.css`, Teenage Engineering principles, one accent `#f05a24`, no yellow, thin Onest + JetBrains Mono. Forms: hairline inputs, pill buttons, error text in plain words.

## Config (env)

`PUBLIC_ORIGIN`, `SESSION_COOKIE` (default `__Host-sid`), `TELEGRAM_LOGIN_BOT_TOKEN`, `TELEGRAM_BOT_USERNAME`, `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_NAME`, `SMTP_HOST/PORT/USER/PASSWORD/FROM` (optional), `BOT_API_URL`, `BOT_API_TOKEN`, `REMNAWAVE_API_URL`, `REMNAWAVE_API_TOKEN`, `SUBSCRIPTION_BASE_URL` (default `https://sub.crs-projects.com`).

## Manual steps for the owner

- BotFather → `/setdomain` for `@crs_vpn_bot` → `vpn.crs-projects.com` (Telegram widget works only on the bot's domain).
- SMTP account for real emails (until then letters sit in `web.outbox`).
