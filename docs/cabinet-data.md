# Cabinet data: bot + panel

The cabinet (`GET /api/cabinet`) is built per request from two sources. The site stores none of it: no sub links, no traffic, no devices.

## Who answers what

| Source | What it gives | Why there |
|---|---|---|
| Bot, `GET {BOT_API_URL}/internal/site/users/{telegram_id}/profile`, header `X-Internal-Token: BOT_API_TOKEN` | user, accounts (`kind` main/obhod, panel user id, plan, device limit, obhod package), payments, stats | the bot owns ownership and money: which panel users belong to this telegram id, what was paid |
| Remnawave panel 3.4.3, `REMNAWAVE_API_URL`, `Authorization: Bearer REMNAWAVE_API_TOKEN` | status, expiry, subscription link, traffic and limit, online and last node, HWID devices, daily usage, per node usage, node list | the panel is the live truth for all of that |

Code: `api/app/gateway/http.py` (bot), `api/app/panel.py` (panel), `api/app/gateway/live.py` (composition), `api/app/gateway/mock.py` (demo). Either URL empty means the mock and the "пример" badge.

## Panel allowlist

Routes and shapes are taken from `@remnawave/backend-contract@3.4.3`. In 3.x users are addressed by the numeric `id`. `PanelClient` calls only:

- `GET /api/users/{id}`
- `GET /api/users?filters=[{"id":"telegramId","value":...}]`: fallback for the main account when the bot gives no panel id. The panel filter is a LIKE, so results are narrowed to the exact telegram id; with several matches the lowest id not taken by another account wins.
- `GET /api/hwid/devices/{id}`
- `POST /api/hwid/devices/delete {userId, hwid}`: the only write.
- `GET /api/bandwidth-stats/users/{id}?start&end`: daily totals (`categories` + `sparklineData`) and per node `series`. Called twice per user: the 30-day window (30 s cache) and the long range for monthly bars, from `max(createdAt, first day of the month 23 months back)` to today (10 min cache, survives a device delete).
- `GET /api/nodes`: only `name`, `countryCode`, `isConnected` leave the client; addresses, ports, IPs never do. Disabled nodes are hidden.

The token itself has full scopes (owner decision); the allowlist in code is the limit. `REMNAWAVE_API_URL` may be given with or without the `/api` suffix.

## Rules

- Ownership: the site asks the bot for the accounts of the signed-in telegram id and only then reads those panel users. A device is deleted only if its hwid is in the fresh device list of one of these accounts.
- Links: `subscriptionUrl` from the panel, scheme and host replaced with `SUBSCRIPTION_BASE_URL` when they differ (the bot does the same).
- Status: panel status in lower case (`active`, `expired`, `disabled`, `limited`). `expireAt` year >= 2099 means lifetime. `days_left` is rounded up.
- Node names: a leading `remnanode-` (any case) is stripped for `nodes`, `traffic_by_node` and `last_node` (`remnanode-nl-2` → `nl-2`).
- Monthly: `traffic_monthly: [{month: "YYYY-MM", main_bytes, obhod_bytes}]`, daily panel totals grouped by `categories[:7]` (dates as the panel returns them, Moscow), from the first month with traffic to the current one, gaps as zeros, at most 24 months. The cabinet waits for the long call at most 2 s; a slower cold call keeps running and fills the cache for the next load, the page shows "еще считается" meanwhile (not a `partial`).
- Lifetime: `traffic.lifetime_used_bytes` = `userTraffic.lifetimeUsedTrafficBytes`.
- Owner preview: `GET /api/cabinet?demo=active|expiring|expired|none` (session required) returns MockGateway data with `demo: true` whatever the gateway; unknown scenario → 400. The web page `/cabinet?demo=...` shows a "пример" bar.
- Traffic: `used_bytes` = `userTraffic.usedTrafficBytes`, `limit_bytes` = `trafficLimitBytes` (0 means none), `reset` from `trafficLimitStrategy`. `month_used_bytes` and the 30-day chart come from bandwidth stats (dates as the panel returns them; the 30-day window ends today, Moscow time).
- Failures: bot down → 503 `bot_unavailable`. Panel down → 200 with `partial: true`, `errors: ["panel"]`, bot data still shown.
- Timeouts and caches: bot 3 s, panel 4 s, panel calls run concurrently. 30 s in-process cache per telegram id (bot) and per panel user id (panel); a device delete drops that user's panel cache.
- Logs: never response bodies, links, tokens or device IPs. Audit keeps the first 6 characters of a deleted hwid.
