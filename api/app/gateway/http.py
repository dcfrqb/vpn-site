"""HTTP client for the bot's internal site API: who owns what, plans, payments.

Only `GET /internal/site/users/{telegram_id}/profile`. Live data comes from the panel.
Never log the response body or the token.
"""

import logging
import time

import httpx
from pydantic import ValidationError

from app.gateway.base import BotAccount, BotProfile, CabinetUser, GatewayUnavailable

log = logging.getLogger(__name__)

TIMEOUT = 3.0
CACHE_TTL = 30.0
_CACHE_MAX = 5000


class HttpBotClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        cache_ttl: float = CACHE_TTL,
    ):
        self._base = base_url.rstrip("/")
        self._token = token
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._ttl = cache_ttl
        # telegram id -> (expires at, profile or None for "bot does not know this user")
        self._cache: dict[int, tuple[float, BotProfile | None]] = {}

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                timeout=TIMEOUT,
                headers={"X-Internal-Token": self._token, "Accept": "application/json"},
                transport=self._transport,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def drop_cache(self, telegram_id: int) -> None:
        self._cache.pop(telegram_id, None)

    async def profile(self, telegram_id: int) -> BotProfile | None:
        hit = self._cache.get(telegram_id)
        now = time.monotonic()
        if hit and hit[0] > now:
            return hit[1]
        try:
            res = await self._http().get(f"/internal/site/users/{int(telegram_id)}/profile")
        except httpx.HTTPError as e:
            log.warning("bot api profile failed: %s", type(e).__name__)
            raise GatewayUnavailable from e
        if res.status_code == 404:
            prof = None
        elif res.status_code == 200:
            try:
                prof = BotProfile.model_validate_json(res.content)
            except ValidationError as e:
                log.warning("bot api profile: unexpected shape (%d errors)", e.error_count())
                raise GatewayUnavailable from e
        else:
            log.warning("bot api profile answered %s", res.status_code)
            raise GatewayUnavailable
        if len(self._cache) >= _CACHE_MAX:
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        self._cache[telegram_id] = (now + self._ttl, prof)
        return prof


class PanelOnlyBotClient:
    """Stand-in while the bot has no profile API: the main account is found in the panel
    by telegram id; payments and the obhod account stay empty and the cabinet says so."""

    offline = True

    async def aclose(self) -> None:
        return None

    def drop_cache(self, telegram_id: int) -> None:
        return None

    async def profile(self, telegram_id: int) -> BotProfile | None:
        return BotProfile(
            user=CabinetUser(telegram_id=telegram_id), accounts=[BotAccount(kind="main")]
        )
