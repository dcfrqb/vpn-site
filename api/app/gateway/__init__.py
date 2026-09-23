"""Single entry point for everything the site takes from the VPN bot.

Right now it is a mock with real prices and plausible network data.
After bot release 3.0 an HTTP implementation replaces it; routers do not change.
"""

from app.config import get_settings
from app.gateway.base import BotGateway
from app.gateway.mock import MockGateway


def get_gateway() -> BotGateway:
    settings = get_settings()
    if settings.bot_api_url:
        raise NotImplementedError("HTTP gateway to the bot arrives with bot release 3.0")
    return MockGateway()
