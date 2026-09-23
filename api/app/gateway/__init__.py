"""Single entry point for everything the site takes from the bot and the panel.

REMNAWAVE_API_URL set: LiveGateway (bot profile + panel live data); without BOT_API_URL the
profile is a panel-only stand-in (main account by telegram id, no payments).
REMNAWAVE_API_URL empty: MockGateway with demo data. Routers do not know which one they got.
"""

from app.config import get_settings
from app.gateway.base import BotGateway
from app.gateway.http import HttpBotClient, PanelOnlyBotClient
from app.gateway.live import LiveGateway
from app.gateway.mock import MockGateway
from app.panel import PanelClient

_live: LiveGateway | None = None
_live_key: tuple[str, ...] | None = None


def get_gateway() -> BotGateway:
    global _live, _live_key
    s = get_settings()
    if not s.remnawave_api_url:
        return MockGateway()
    key = (
        s.bot_api_url,
        s.bot_api_token,
        s.remnawave_api_url,
        s.remnawave_api_token,
        s.subscription_base_url,
    )
    if _live is None or _live_key != key:
        # One shared pair of clients and caches per process; rebuilt only if the config changes.
        _live = LiveGateway(
            HttpBotClient(s.bot_api_url, s.bot_api_token)
            if s.bot_api_url
            else PanelOnlyBotClient(),
            PanelClient(s.remnawave_api_url, s.remnawave_api_token),
            s.subscription_base_url,
        )
        _live_key = key
    return _live


def is_demo(gw: BotGateway) -> bool:
    return isinstance(gw, MockGateway)


async def close_gateway() -> None:
    global _live, _live_key
    if _live is not None:
        await _live.aclose()
    _live = _live_key = None
