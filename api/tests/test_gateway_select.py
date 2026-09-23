from app.config import get_settings
from app.gateway import MockGateway, close_gateway, get_gateway
from app.gateway.http import PanelOnlyBotClient


def test_gateway_selection(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "remnawave_api_url", "")
    monkeypatch.setattr(s, "bot_api_url", "")
    assert isinstance(get_gateway(), MockGateway)
    monkeypatch.setattr(s, "remnawave_api_url", "https://panel.example/api")
    gw = get_gateway()
    assert isinstance(gw.bot, PanelOnlyBotClient)


async def _profile():
    return await PanelOnlyBotClient().profile(42)


def test_panel_only_profile():
    import asyncio

    p = asyncio.run(_profile())
    assert p.user.telegram_id == 42
    assert [a.kind for a in p.accounts] == ["main"] and p.accounts[0].panel_id is None
    asyncio.run(close_gateway())
