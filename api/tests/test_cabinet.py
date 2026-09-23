import asyncio
from datetime import UTC, datetime

from app.gateway.mock import MockGateway
from tests.conftest import register, telegram_payload


def test_cabinet_requires_session(client):
    assert client.get("/api/cabinet").status_code == 401


def test_cabinet_unlinked(client):
    register(client)
    assert client.get("/api/cabinet").json() == {
        "linked": False,
        "subscription": None,
        "devices": [],
        "payments": [],
        "nodes": [],
        "demo": True,
    }


def test_cabinet_linked(client):
    client.post("/api/auth/telegram", json=telegram_payload(1001))
    cab = client.get("/api/cabinet").json()
    assert cab["linked"] is True and cab["demo"] is True
    sub = cab["subscription"]
    assert sub["plan"] in {"lite", "standard", "pro"}
    assert set(sub) == {
        "plan",
        "status",
        "valid_until",
        "days_left",
        "device_limit",
        "sub_url",
        "traffic_month_gb",
    }
    assert set(cab["payments"][0]) == {"date", "plan", "months", "amount_rub", "status"}
    assert set(cab["nodes"][0]) == {"name", "country", "online", "ping_ms"}
    assert set(cab["devices"][0]) == {"name", "last_seen_at"}
    assert client.get("/api/cabinet").json() == cab


def test_mock_cabinet_is_deterministic_and_consistent():
    gw = MockGateway()
    plans = {p.code: p for p in asyncio.run(gw.list_plans())}
    seen = set()
    for tg_id in range(1, 60):
        cab = asyncio.run(gw.cabinet(tg_id))
        assert cab == asyncio.run(gw.cabinet(tg_id))
        sub = cab.subscription
        plan = plans[sub.plan]
        seen.add(sub.plan)
        assert sub.valid_until > datetime.now(UTC) and sub.days_left > 0
        assert sub.device_limit == plan.device_limit
        assert 2 <= len(cab.devices) <= 4
        assert 1 <= len(cab.payments) <= 4
        assert all(p.amount_rub == plan.prices[p.months] for p in cab.payments)
        assert {n.country for n in cab.nodes} >= set(plan.countries)
        assert all(n.ping_ms and n.ping_ms > 0 for n in cab.nodes)
    assert seen == {"lite", "standard", "pro"}
