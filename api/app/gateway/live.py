"""Live cabinet: the bot says what belongs to whom, the panel says how it is right now.

Bot (HttpBotClient): user, accounts (kind -> panel user id, plan, device limit, package),
payments, stats. Panel (PanelClient): status, expiry, link, traffic, devices, usage, nodes.
The result has the same shape as the mock (BotCabinet), so routers and the web do not care.
"""

import asyncio
import logging
import math
import re
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from app.gateway.base import (
    BotAccount,
    BotCabinet,
    CabinetDevice,
    CabinetNode,
    CabinetSubscription,
    GatewayUnavailable,
    NetworkStatus,
    NodeTraffic,
    Plan,
    SubTraffic,
    TrafficDay,
    TrafficMonth,
)
from app.gateway.http import HttpBotClient
from app.gateway.mock import MockGateway
from app.panel import PanelClient, PanelDevice, PanelNode, PanelUnavailable, PanelUsage, PanelUser
from app.panel import gather_safe as gather

log = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
DAYS = 30
MONTHS = 24  # monthly bars go back at most this many months, the current one included
MONTHLY_WAIT = 2.0  # seconds the cabinet waits for the long range; it keeps loading after that
LIFETIME_YEAR = 2099
_RESET = {"MONTH": "month", "MONTH_ROLLING": "month", "DAY": "day", "WEEK": "week"}


def rewrite_sub_url(url: str, base: str) -> str:
    """Keep the path (the token), force scheme and host of SUBSCRIPTION_BASE_URL (as the bot)."""
    if not base:
        return url
    b, u = urlsplit(base), urlsplit(url)
    if (u.scheme, u.netloc) == (b.scheme, b.netloc):
        return url
    prefix = b.path.rstrip("/")
    return urlunsplit((b.scheme, b.netloc, prefix + u.path, u.query, ""))


_NODE_PREFIX = re.compile(r"^remnanode-", re.IGNORECASE)


def node_label(name: str) -> str:
    """Panel node names look like "remnanode-nl-2"; people see "nl-2"."""
    return _NODE_PREFIX.sub("", name.strip()) or name


def month_start(today: date, back: int) -> date:
    """First day of the month `back` months before today's month."""
    idx = today.year * 12 + today.month - 1 - back
    return date(idx // 12, idx % 12 + 1, 1)


def monthly(usages: dict[str, PanelUsage], today: date) -> list[TrafficMonth]:
    """Daily panel totals grouped by YYYY-MM, from the first month with traffic to the current
    month (gaps filled with zeros), at most MONTHS months."""
    sums: dict[str, dict[str, int]] = {}
    for kind, u in usages.items():
        if kind not in ("main", "obhod"):
            continue
        for cat, value in zip(u.categories, u.sparklineData, strict=False):
            key = cat[:7]
            if len(key) != 7 or not value:
                continue
            row = sums.setdefault(key, {"main": 0, "obhod": 0})
            row[kind] += int(value)
    if not sums:
        return []
    oldest = month_start(today, MONTHS - 1)
    first = max(min(sums), f"{oldest.year:04d}-{oldest.month:02d}")
    out = []
    d = oldest
    while d <= today:
        key = f"{d.year:04d}-{d.month:02d}"
        if key >= first:
            row = sums.get(key, {})
            out.append(
                TrafficMonth(
                    month=key, main_bytes=row.get("main", 0), obhod_bytes=row.get("obhod", 0)
                )
            )
        d = month_start(d, -1)
    return out


def _app(ua: str | None) -> str | None:
    # "Happ/3.1.0/ios CFNetwork/..." -> "Happ/3.1.0"; the rest is noise for a person.
    if not ua:
        return None
    head = ua.split()[0]
    parts = head.split("/")
    return "/".join(parts[:2])[:40]


class LiveGateway:
    def __init__(self, bot: HttpBotClient, panel: PanelClient, sub_base: str):
        self.bot, self.panel, self.sub_base = bot, panel, sub_base
        self._static = MockGateway()  # plans and the public network block stay static for now
        self._bg: set[asyncio.Future] = set()  # long usage loads that outlived a request

    async def aclose(self) -> None:
        await self.bot.aclose()
        await self.panel.aclose()

    async def list_plans(self) -> list[Plan]:
        return await self._static.list_plans()

    async def network_status(self) -> NetworkStatus:
        return await self._static.network_status()

    async def _panel_ids(self, telegram_id: int, accounts: list[BotAccount]) -> dict[str, int]:
        """kind -> panel user id. A main account without a mapping is looked up by telegram id."""
        ids = {a.kind: a.panel_id for a in accounts if a.panel_id is not None}
        if "main" not in ids and any(a.kind == "main" for a in accounts):
            found = [u for u in await self.panel.find_user_by_telegram(telegram_id)]
            taken = set(ids.values())
            free = [u for u in found if u.id not in taken]
            if free:
                ids["main"] = free[0].id
        return ids

    async def cabinet(self, telegram_id: int) -> BotCabinet | None:
        profile = await self.bot.profile(telegram_id)  # GatewayUnavailable -> 503 upstream
        if profile is None:
            return None
        # "bot": no bot profile API yet, so no payments and no obhod account
        errors: set[str] = {"bot"} if getattr(self.bot, "offline", False) else set()
        now = datetime.now(UTC)
        today = now.astimezone(MSK).date()
        first = today - timedelta(days=DAYS - 1)
        start = min(first, today.replace(day=1))

        try:
            ids = await self._panel_ids(telegram_id, profile.accounts)
        except PanelUnavailable:
            ids = {}
            errors.add("panel")

        kinds = [a.kind for a in profile.accounts if a.kind in ids]
        results = await gather(
            self.panel.nodes(),
            *(self.panel.get_user(ids[k]) for k in kinds),
            *(self.panel.devices(ids[k]) for k in kinds),
            *(self.panel.usage(ids[k], start, today) for k in kinds),
        )

        def ok(value, default):
            if isinstance(value, BaseException):
                if not isinstance(value, PanelUnavailable):
                    log.warning("panel call crashed: %s", type(value).__name__)
                errors.add("panel")
                return default
            return value

        n = len(kinds)
        nodes: list[PanelNode] = ok(results[0], [])
        users: dict[str, PanelUser | None] = {
            k: ok(results[1 + i], None) for i, k in enumerate(kinds)
        }
        devices: dict[str, list[PanelDevice]] = {
            k: ok(results[1 + n + i], []) for i, k in enumerate(kinds)
        }
        usage: dict[str, PanelUsage] = {
            k: ok(results[1 + 2 * n + i], PanelUsage()) for i, k in enumerate(kinds)
        }
        node_name = {nd.uuid: node_label(nd.name) for nd in nodes}

        # Monthly bars: one longer, separately cached call per user, from its creation date
        # (never more than MONTHS back). A failure here only hides the monthly view.
        oldest = month_start(today, MONTHS - 1)
        long_kinds = [k for k in kinds if users.get(k) is not None]
        long_usage = await self._long_usage(
            {k: (ids[k], self._long_start(users[k], oldest)) for k in long_kinds}, today
        )

        daily = {k: self._daily(usage[k]) for k in kinds}
        subs = []
        for acc in profile.accounts:
            u = users.get(acc.kind)
            if u is None and acc.kind in ids and "panel" not in errors:
                continue  # the bot points to a panel user that no longer exists
            subs.append(self._subscription(acc, u, daily.get(acc.kind, {}), today, now, node_name))

        days = [first + timedelta(days=i) for i in range(DAYS)]
        traffic_daily = [
            TrafficDay(
                date=d,
                main_bytes=daily.get("main", {}).get(d, 0),
                obhod_bytes=daily.get("obhod", {}).get(d, 0),
            )
            for d in days
        ]

        return BotCabinet(
            generated_at=now,
            partial=bool(errors),
            errors=sorted(errors),
            user=profile.user,
            subscriptions=subs,
            devices=[
                CabinetDevice(
                    subscription=k,
                    hwid=d.hwid,
                    platform=d.platform,
                    os_version=d.osVersion,
                    model=d.deviceModel,
                    app=_app(d.userAgent),
                    first_seen_at=d.createdAt,
                    last_seen_at=d.updatedAt,
                )
                for k in kinds
                for d in devices[k]
            ],
            traffic_daily=traffic_daily,
            traffic_by_node=self._by_node([usage[k] for k in kinds], set(days)),
            traffic_monthly=monthly(long_usage, today),
            payments=profile.payments,
            stats=profile.stats,
            nodes=[
                CabinetNode(
                    name=node_label(nd.name),
                    country=(nd.countryCode or "").lower() or None,
                    online=nd.isConnected,
                )
                for nd in nodes
                if not nd.isDisabled
            ],
        )

    async def _long_usage(
        self, wanted: dict[str, tuple[int, date]], today: date
    ) -> dict[str, PanelUsage]:
        """The long range per account. Waits at most MONTHLY_WAIT: a cold, slow panel call keeps
        running in the background and fills the 10 min cache for the next page load."""
        if not wanted:
            return {}
        kinds = list(wanted)
        task = asyncio.ensure_future(
            gather(
                *(self.panel.usage(uid, start, today, long=True) for uid, start in wanted.values())
            )
        )
        self._bg.add(task)
        task.add_done_callback(self._bg.discard)
        try:
            results = await asyncio.wait_for(asyncio.shield(task), MONTHLY_WAIT)
        except TimeoutError:
            log.info("panel monthly usage is slow, served without it")
            return {}
        out: dict[str, PanelUsage] = {}
        for k, r in zip(kinds, results, strict=True):
            if isinstance(r, BaseException):
                log.warning("panel monthly usage failed: %s", type(r).__name__)
            else:
                out[k] = r
        return out

    @staticmethod
    def _long_start(u: PanelUser | None, oldest: date) -> date:
        if u is None or u.createdAt is None:
            return oldest
        return max(oldest, u.createdAt.astimezone(MSK).date())

    @staticmethod
    def _daily(u: PanelUsage) -> dict[date, int]:
        out: dict[date, int] = {}
        for cat, value in zip(u.categories, u.sparklineData, strict=False):
            try:
                out[date.fromisoformat(cat[:10])] = int(value)
            except ValueError:
                continue
        return out

    @staticmethod
    def _by_node(usages: list[PanelUsage], window: set[date]) -> list[NodeTraffic]:
        acc: dict[str, NodeTraffic] = {}
        for u in usages:
            dates = []
            for cat in u.categories:
                try:
                    dates.append(date.fromisoformat(cat[:10]))
                except ValueError:
                    dates.append(None)
            for s in u.series:
                total = sum(v for d, v in zip(dates, s.data, strict=False) if d in window)
                name = node_label(s.name)
                row = acc.setdefault(
                    name,
                    NodeTraffic(node=name, country=(s.countryCode or "").lower() or None),
                )
                row.bytes_30d += int(total)
        return sorted((r for r in acc.values() if r.bytes_30d > 0), key=lambda r: -r.bytes_30d)

    def _subscription(
        self,
        acc: BotAccount,
        u: PanelUser | None,
        daily: dict[date, int],
        today: date,
        now: datetime,
        node_name: dict[str, str],
    ) -> CabinetSubscription:
        base = dict(
            kind=acc.kind,
            plan_code=acc.plan_code,
            plan_title=acc.plan_title,
            legacy=acc.legacy,
            device_limit=acc.device_limit,
            package=acc.package,
        )
        if u is None:  # panel is down: what the bot knows, no live fields
            return CabinetSubscription(status="unknown", **base)
        lifetime = u.expireAt.year >= LIFETIME_YEAR
        days_left = None
        if not lifetime:
            days_left = max(0, math.ceil((u.expireAt - now).total_seconds() / 86400))
        month = sum(v for d, v in daily.items() if (d.year, d.month) == (today.year, today.month))
        if u.hwidDeviceLimit:
            base["device_limit"] = u.hwidDeviceLimit
        return CabinetSubscription(
            **base,
            status=u.status.lower(),
            valid_until=None if lifetime else u.expireAt,
            is_lifetime=lifetime,
            days_left=days_left,
            sub_url=rewrite_sub_url(u.subscriptionUrl, self.sub_base),
            traffic=SubTraffic(
                used_bytes=u.userTraffic.usedTrafficBytes,
                limit_bytes=u.trafficLimitBytes or None,
                reset=_RESET.get(u.trafficLimitStrategy, "none"),
                month_used_bytes=month if daily else None,
                lifetime_used_bytes=u.userTraffic.lifetimeUsedTrafficBytes,
            ),
            online_at=u.userTraffic.onlineAt,
            last_node=node_name.get(u.userTraffic.lastConnectedNodeUuid or ""),
        )

    async def delete_device(self, telegram_id: int, hwid: str) -> bool:
        """Delete only a hwid found among the devices of this user's own panel accounts."""
        profile = await self.bot.profile(telegram_id)
        if profile is None:
            return False
        try:
            ids = await self._panel_ids(telegram_id, profile.accounts)
            for user_id in ids.values():
                if any(d.hwid == hwid for d in await self.panel.devices(user_id, fresh=True)):
                    return await self.panel.delete_device(user_id, hwid)
        except PanelUnavailable as e:
            raise GatewayUnavailable from e
        return False
