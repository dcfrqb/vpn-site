"""Read-mostly client for the Remnawave panel (3.4.3).

Routes and shapes come from `@remnawave/backend-contract@3.4.3` (api/routes.js, commands/*):
in 3.x users are addressed by the numeric `id`, not by uuid.

Allowlist, nothing else is called:
- GET  /api/users/{id}                       user (subscriptionUrl, userTraffic, limits, expireAt)
- GET  /api/users?filters=[telegramId]       fallback lookup of the main user by telegram id
- GET  /api/hwid/devices/{id}                HWID devices of a user
- POST /api/hwid/devices/delete {userId,hwid} the only write
- GET  /api/bandwidth-stats/users/{id}       daily usage by date range, per node series
                                             (30 days: 30 s cache; up to 24 months: 10 min cache)
- GET  /api/nodes                            nodes: only name, country and status leave this module

Never log response bodies (they hold subscription links) or the token.
"""

import asyncio
import json
import logging
import time
from datetime import date, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

log = logging.getLogger(__name__)

TIMEOUT = 4.0
CACHE_TTL = 30.0
LONG_TTL = 600.0  # the long bandwidth range (monthly bars) is heavier and changes slowly


class PanelUnavailable(Exception):  # noqa: N818 - reads better at the call site
    """The panel did not answer, answered 5xx/auth error or with an unexpected shape."""


class _Tolerant(BaseModel):
    model_config = ConfigDict(extra="ignore")


class PanelTraffic(_Tolerant):
    usedTrafficBytes: int = 0  # noqa: N815 - panel field names
    lifetimeUsedTrafficBytes: int | None = None  # noqa: N815
    onlineAt: datetime | None = None  # noqa: N815
    lastConnectedNodeUuid: str | None = None  # noqa: N815


class PanelUser(_Tolerant):
    id: int
    status: str  # ACTIVE | DISABLED | LIMITED | EXPIRED
    trafficLimitBytes: int = 0  # noqa: N815
    trafficLimitStrategy: str = "NO_RESET"  # noqa: N815
    expireAt: datetime  # noqa: N815
    telegramId: int | None = None  # noqa: N815
    hwidDeviceLimit: int | None = None  # noqa: N815
    subscriptionUrl: str  # noqa: N815
    userTraffic: PanelTraffic = PanelTraffic()  # noqa: N815
    createdAt: datetime | None = None  # noqa: N815


class PanelDevice(_Tolerant):
    # requestIp is deliberately not mapped: it never leaves the panel client.
    hwid: str
    userId: int  # noqa: N815
    platform: str | None = None
    osVersion: str | None = None  # noqa: N815
    deviceModel: str | None = None  # noqa: N815
    userAgent: str | None = None  # noqa: N815
    createdAt: datetime | None = None  # noqa: N815
    updatedAt: datetime | None = None  # noqa: N815


class PanelSeries(_Tolerant):
    uuid: str | None = None
    name: str
    countryCode: str | None = None  # noqa: N815
    total: int = 0
    data: list[int] = []


class PanelUsage(_Tolerant):
    categories: list[str] = []  # dates, YYYY-MM-DD
    sparklineData: list[int] = []  # noqa: N815 - daily totals, same order as categories
    series: list[PanelSeries] = []  # per node


class PanelNode(_Tolerant):
    # address, port, ips, provider and the rest are dropped by the model on purpose.
    uuid: str
    name: str
    countryCode: str | None = None  # noqa: N815
    isConnected: bool = False  # noqa: N815
    isDisabled: bool = False  # noqa: N815


class PanelClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        cache_ttl: float = CACHE_TTL,
        long_ttl: float = LONG_TTL,
    ):
        # REMNAWAVE_API_URL may be "https://host" or "https://host/api"; paths below carry /api.
        self._base = base_url.rstrip("/")
        if self._base.endswith("/api"):
            self._base = self._base[:-4]
        self._token = token
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._ttl = cache_ttl
        self._long_ttl = long_ttl
        self._cache: dict[tuple, tuple[float, Any]] = {}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                timeout=TIMEOUT,
                headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _call(self, method: str, path: str, **kw) -> httpx.Response:
        try:
            res = await self._http().request(method, path, **kw)
        except httpx.HTTPError as e:
            log.warning("panel %s failed: %s", method, type(e).__name__)
            raise PanelUnavailable from e
        if res.status_code >= 500 or res.status_code in (400, 401, 403, 429):
            log.warning("panel %s answered %s", method, res.status_code)
            raise PanelUnavailable
        return res

    @staticmethod
    def _body(res: httpx.Response) -> Any:
        try:
            return res.json()["response"]
        except (ValueError, KeyError, TypeError) as e:
            raise PanelUnavailable from e

    async def _cached(self, key: tuple, load, ttl: float | None = None):
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit and hit[0] > now:
            return hit[1]
        value = await load()
        if len(self._cache) > 5000:
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        self._cache[key] = (now + (self._ttl if ttl is None else ttl), value)
        return value

    def drop(self, user_id: int) -> None:
        # The long usage range survives a device delete: it does not depend on devices.
        for k in [k for k in self._cache if len(k) > 1 and k[1] == user_id and k[0] != "usage_m"]:
            self._cache.pop(k, None)

    # ---------- allowlisted calls ----------

    async def get_user(self, user_id: int) -> PanelUser | None:
        async def load():
            res = await self._call("GET", f"/api/users/{int(user_id)}")
            if res.status_code == 404:
                return None
            return self._parse(PanelUser, self._body(res))

        return await self._cached(("user", user_id), load)

    async def find_user_by_telegram(self, telegram_id: int) -> list[PanelUser]:
        """All panel users with exactly this telegramId (the filter itself is a LIKE)."""

        async def load():
            filters = json.dumps([{"id": "telegramId", "value": str(int(telegram_id))}])
            res = await self._call(
                "GET", "/api/users", params={"start": 0, "size": 25, "filters": filters}
            )
            if res.status_code == 404:
                return []
            users = self._body(res).get("users", [])
            found = [self._parse(PanelUser, u) for u in users]
            return sorted((u for u in found if u.telegramId == telegram_id), key=lambda u: u.id)

        return await self._cached(("tg", telegram_id), load)

    async def devices(self, user_id: int, *, fresh: bool = False) -> list[PanelDevice]:
        async def load():
            res = await self._call("GET", f"/api/hwid/devices/{int(user_id)}")
            if res.status_code == 404:
                return []
            return [self._parse(PanelDevice, d) for d in self._body(res).get("devices", [])]

        if fresh:
            self._cache.pop(("devices", user_id), None)
        return await self._cached(("devices", user_id), load)

    async def delete_device(self, user_id: int, hwid: str) -> bool:
        res = await self._call(
            "POST", "/api/hwid/devices/delete", json={"userId": int(user_id), "hwid": hwid}
        )
        self.drop(user_id)
        if res.status_code == 404:
            return False
        if res.status_code >= 300:
            raise PanelUnavailable
        return True

    async def usage(
        self, user_id: int, start: date, end: date, *, long: bool = False
    ) -> PanelUsage:
        """Daily usage. `long=True`: the monthly range, same route, cached for LONG_TTL."""

        async def load():
            res = await self._call(
                "GET",
                f"/api/bandwidth-stats/users/{int(user_id)}",
                params={"start": start.isoformat(), "end": end.isoformat(), "topNodesLimit": 50},
            )
            if res.status_code == 404:
                return PanelUsage()
            return self._parse(PanelUsage, self._body(res))

        if long:
            return await self._cached(("usage_m", user_id, start, end), load, self._long_ttl)
        return await self._cached(("usage", user_id, start, end), load)

    async def nodes(self) -> list[PanelNode]:
        async def load():
            res = await self._call("GET", "/api/nodes")  # contract: /api/nodes/, both answer
            body = self._body(res)
            if not isinstance(body, list):
                raise PanelUnavailable
            return [self._parse(PanelNode, n) for n in body]

        return await self._cached(("nodes",), load)

    @staticmethod
    def _parse(model, data):
        try:
            return model.model_validate(data)
        except ValidationError as e:
            log.warning("panel: unexpected %s shape (%d errors)", model.__name__, e.error_count())
            raise PanelUnavailable from e


def gather_safe(*aws):
    """asyncio.gather that returns PanelUnavailable instances instead of raising them."""
    return asyncio.gather(*aws, return_exceptions=True)
