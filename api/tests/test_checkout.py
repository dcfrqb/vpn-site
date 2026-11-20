from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.checkout_bridge import bridge
from app.config import get_settings
from app.errors import ApiError
from app.gateway import get_gateway
from app.gateway.base import BotProfile, CabinetUser, Plan
from app.gateway.live import LiveGateway
from app.gateway.mock import MockGateway
from app.main import app
from tests.conftest import register


@pytest.fixture
def billing(client, monkeypatch):
    settings = get_settings()
    previous = settings.site_checkout_enabled
    settings.site_checkout_enabled = True
    request = AsyncMock(return_value={"enabled": True})
    monkeypatch.setattr(bridge, "request", request)
    yield request
    settings.site_checkout_enabled = previous
    app.dependency_overrides.clear()


def test_disabled_and_authentication(client):
    assert (
        client.post("/api/checkout/quote", json={"plan_code": "lite", "months": 1}).status_code
        == 401
    )
    register(client)
    assert (
        client.post("/api/checkout/quote", json={"plan_code": "lite", "months": 1}).status_code
        == 503
    )


def test_identity_is_from_session_not_browser(client, billing):
    account = register(client).json()["account"]
    assert (
        client.post("/api/checkout/quote", json={"plan_code": "lite", "months": 1}).status_code
        == 200
    )
    assert billing.call_args.args[2] == {
        "account_id": account["id"],
        "telegram_id": None,
        "plan_code": "lite",
        "months": 1,
    }
    for forged in [{"account_id": str(uuid4())}, {"telegram_id": 123}, {"amount_rub": 1}]:
        assert (
            client.post(
                "/api/checkout/quote", json={"plan_code": "lite", "months": 1, **forged}
            ).status_code
            == 422
        )


def test_order_scoped_to_account(client, billing):
    account = register(client).json()["account"]
    key = str(uuid4())
    body = {"plan_code": "lite", "months": 1, "order_id": key, "expected_amount_rub": 129}
    assert client.post("/api/checkout/orders", json=body).status_code == 200
    assert billing.call_args.args[2] == {**body, "account_id": account["id"], "telegram_id": None}
    assert client.get("/api/checkout/orders/" + key).status_code == 200
    assert (
        billing.call_args.args[1]
        == f"/internal/site/checkout/accounts/{account['id']}/orders/{key}"
    )


def test_owner_error_not_hidden(client, billing):
    register(client)
    key = str(uuid4())
    billing.side_effect = ApiError(404, "order_not_found")
    assert client.get("/api/checkout/orders/" + key).status_code == 404


def test_account_without_telegram_gets_live_profile(client, billing, monkeypatch):
    register(client)
    gw = LiveGateway(None, None, "https://sub.example.com")
    data = __import__("asyncio").run(MockGateway().cabinet(0))
    gw.cabinet_profile = AsyncMock(return_value=data)
    app.dependency_overrides[get_gateway] = lambda: gw
    profile = BotProfile(user=CabinetUser(telegram_id=None))
    monkeypatch.setattr(bridge, "profile", AsyncMock(return_value=profile))
    result = client.get("/api/cabinet")
    assert result.status_code == 200
    assert result.json()["linked"] is True and result.json()["demo"] is False
    gw.cabinet_profile.assert_awaited_once_with(profile)


def test_empty_web_profile_is_not_telegram_gate(client, billing, monkeypatch):
    register(client)
    gw = LiveGateway(None, None, "https://sub.example.com")
    app.dependency_overrides[get_gateway] = lambda: gw
    monkeypatch.setattr(bridge, "profile", AsyncMock(return_value=None))
    assert client.get("/api/cabinet").json() == {"linked": True, "demo": False, "data": None}


def test_web_device_delete_still_uses_owned_profile(client, billing, monkeypatch):
    register(client)
    gw = LiveGateway(None, None, "https://sub.example.com")
    gw.delete_device_profile = AsyncMock(return_value=False)
    app.dependency_overrides[get_gateway] = lambda: gw
    profile = BotProfile(user=CabinetUser(telegram_id=None))
    monkeypatch.setattr(bridge, "profile", AsyncMock(return_value=profile))
    assert client.delete("/api/cabinet/devices/foreign").status_code == 404
    gw.delete_device_profile.assert_awaited_once_with(profile, "foreign")


def test_catalog_uses_bot_prices_when_enabled(client, billing, monkeypatch):
    plan = Plan(code="lite", title="Lite", device_limit=3, countries=["Финляндия"], prices={1: 129})
    monkeypatch.setattr(bridge, "catalog", AsyncMock(return_value=[plan]))
    assert client.get("/api/plans").json()[0]["prices"] == {"1": 129}
