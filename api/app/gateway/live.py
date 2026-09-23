"""Live cabinet: the bot says what belongs to whom, the panel says how it is right now.

Bot (HttpBotClient): user, accounts (kind -> panel user id, plan, device limit, package),
payments, stats. Panel (PanelClient): status, expiry, link, traffic, devices, usage, nodes.
The result has the same shape as the mock (BotCabinet), so routers and the web do not care.
"""

import logging
import math
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
)
from app.gateway.http import HttpBotClient
from app.gateway.mock import MockGateway
from app.panel import PanelClient, PanelDevice, PanelNode, PanelUnavailable, PanelUsage, PanelUser
from app.panel import gather_safe as gather

log = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))
DAYS = 30
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
        node_name = {nd.uuid: nd.name for nd in nodes}

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
            payments=profile.payments,
            stats=profile.stats,
            nodes=[
                CabinetNode(
                    name=nd.name,
                    country=(nd.countryCode or "").lower() or None,
                    online=nd.isConnected,
                )
                for nd in nodes
                if not nd.isDisabled
            ],
        )

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
                row = acc.setdefault(
                    s.name,
                    NodeTraffic(node=s.name, country=(s.countryCode or "").lower() or None),
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
