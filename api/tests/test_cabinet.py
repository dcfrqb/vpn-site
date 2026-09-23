import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.gateway import get_gateway, is_demo
from app.gateway.base import BotCabinet, GatewayUnavailable
from app.gateway.http import HttpBotClient
from app.gateway.live import LiveGateway, rewrite_sub_url
from app.gateway.mock import MockGateway
from app.main import app
from app.panel import PanelClient, PanelUnavailable
from tests.conftest import register, run_sql, telegram_payload

GB = 1024**3
NODES = {"nl-1", "nl-2", "fr-1", "fr-2", "us-3", "es-1", "ru-1"}

TG = 77
MAIN_ID, OBHOD_ID, OTHER_ID = 101, 102, 999

BOT_PROFILE = {
    "user": {"telegram_id": TG, "username": "name", "first_name": "Name", "customer_since": None},
    "accounts": [
        {
            "kind": "main",
            "remna_uuid": str(MAIN_ID),
            "plan_code": "standard",
            "plan_title": "Standard",
            "legacy": False,
            "device_limit": 5,
        },
        {
            "kind": "obhod",
            "remna_id": OBHOD_ID,
            "plan_code": "pro",
            "plan_title": "RU-вход",
            "device_limit": 10,
            "package": {"code": "obhod_250", "until": None, "limit_bytes": 250 * GB},
        },
    ],
    "payments": [
        {
            "id": 481,
            "created_at": "2026-09-01T10:00:00Z",
            "paid_at": None,
            "provider": "yookassa",
            "status": "pending",
            "amount_rub": 249.0,
            "plan_code": None,
            "period_months": None,
            "kind": "subscription",
            "description": "Standard, 1 мес",
        }
    ],
    "stats": {
        "payments_count": 0,
        "paid_total_rub": 0,
        "first_payment_at": None,
        "last_payment_at": None,
    },
    "future_block": [1, 2, 3],
}

NODE_UUID = "11111111-1111-4111-8111-111111111111"


def panel_user(uid, *, expire="2026-10-28T00:00:00.000Z", limit=0, strategy="NO_RESET", tg=TG):
    """UsersSchema + ExtendedUsersSchema of @remnawave/backend-contract@3.4.3."""
    return {
        "id": uid,
        "shortUuid": f"short{uid}",
        "username": f"u{uid}",
        "status": "ACTIVE",
        "trafficLimitBytes": limit,
        "trafficLimitStrategy": strategy,
        "expireAt": expire,
        "telegramId": tg,
        "email": None,
        "description": None,
        "tag": None,
        "hwidDeviceLimit": None,
        "externalSquadUuid": None,
        "trojanPassword": "x",
        "vlessUuid": "22222222-2222-4222-8222-222222222222",
        "ssPassword": "x",
        "lastTriggeredThreshold": 0,
        "subRevokedAt": None,
        "lastTrafficResetAt": None,
        "createdAt": "2025-12-01T10:00:00.000Z",
        "updatedAt": "2026-09-01T10:00:00.000Z",
        "subscriptionUrl": f"https://panel-sub.internal.example/secret{uid}",
        "activeInternalSquads": [],
        "userTraffic": {
            "usedTrafficBytes": 5 * GB,
            "lifetimeUsedTrafficBytes": 50 * GB,
            "onlineAt": "2026-09-23T11:58:00.000Z",
            "firstConnectedAt": None,
            "lastConnectedNodeUuid": NODE_UUID,
        },
    }


def panel_device(uid, hwid):
    return {
        "hwid": hwid,
        "userId": uid,
        "platform": "iOS",
        "osVersion": "19.0",
        "deviceModel": "iPhone16,2",
        "userAgent": "Happ/3.1.0/ios CFNetwork/1",
        "requestIp": "203.0.113.7",
        "createdAt": "2026-08-01T10:00:00.000Z",
        "updatedAt": "2026-09-23T11:00:00.000Z",
    }


def panel_usage(days=3):
    from datetime import timedelta

    from app.gateway.live import MSK

    today = datetime.now(UTC).astimezone(MSK).date()
    cats = [(today - timedelta(days=days - 1 - i)).isoformat() for i in range(days)]
    return {
        "categories": cats,
        "sparklineData": [GB] * days,
        "topNodes": [],
        "series": [
            {
                "uuid": NODE_UUID,
                "name": "nl-1",
                "color": "#fff",
                "countryCode": "NL",
                "total": days * GB,
                "data": [GB] * days,
            }
        ],
    }


PANEL_NODE = {
    "uuid": NODE_UUID,
    "id": 1,
    "name": "nl-1",
    "address": "198.51.100.10",
    "port": 2222,
    "isConnected": True,
    "isDisabled": False,
    "countryCode": "NL",
    "ips": [],
}


class FakePanel:
    """Remnawave 3.4.3 over httpx.MockTransport. `down` makes every call fail."""

    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.users = {
            MAIN_ID: panel_user(MAIN_ID),
            OBHOD_ID: panel_user(OBHOD_ID, limit=100 * GB, strategy="MONTH"),
        }
        self.devices = {
            MAIN_ID: [panel_device(MAIN_ID, "own/hw 1")],
            OBHOD_ID: [],
            OTHER_ID: [panel_device(OTHER_ID, "foreign")],
        }
        self.down = False
        self.deleted: list[dict] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        if self.down:
            return httpx.Response(502)
        path = req.url.path
        ok = lambda body: httpx.Response(200, json={"response": body})  # noqa: E731
        if path == "/api/nodes":
            return ok([PANEL_NODE])
        if path == "/api/users":
            flt = json.loads(req.url.params["filters"])[0]
            users = [
                u for u in self.users.values() if str(u["telegramId"]).startswith(flt["value"])
            ]
            return ok({"users": users, "total": len(users)})
        if path.startswith("/api/users/"):
            uid = int(path.rsplit("/", 1)[1])
            if uid not in self.users:
                return httpx.Response(404, json={"message": "not found"})
            return ok(self.users[uid])
        if path == "/api/hwid/devices/delete":
            body = json.loads(req.content)
            self.deleted.append(body)
            devs = self.devices[body["userId"]]
            devs[:] = [d for d in devs if d["hwid"] != body["hwid"]]
            return ok({"total": len(devs), "devices": devs})
        if path.startswith("/api/hwid/devices/"):
            devs = self.devices.get(int(path.rsplit("/", 1)[1]), [])
            return ok({"total": len(devs), "devices": devs})
        if path.startswith("/api/bandwidth-stats/users/"):
            return ok(panel_usage())
        return httpx.Response(404)


class FakeBot:
    """httpx.MockTransport handler for the bot profile endpoint."""

    def __init__(self, answer=(200, BOT_PROFILE)):
        self.answer, self.calls = answer, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        status, body = self.answer
        return httpx.Response(status, json=body)


def make_bot(bot: FakeBot, **kw) -> HttpBotClient:
    return HttpBotClient("http://bot:8001/", "tok-123", transport=httpx.MockTransport(bot), **kw)


def make_panel(panel: FakePanel, **kw) -> PanelClient:
    return PanelClient(
        "http://panel:3000/api", "panel-tok", transport=httpx.MockTransport(panel), **kw
    )


def make_live(bot=None, panel=None) -> LiveGateway:
    return LiveGateway(
        make_bot(bot or FakeBot()), make_panel(panel or FakePanel()), "https://sub.example.com"
    )


def run(coro):
    return asyncio.run(coro)


# ---------- mock gateway ----------


def test_mock_cabinet_shape_and_determinism():
    gw = MockGateway()
    kinds = set()
    for tg_id in range(1, 60):
        cab = run(gw.cabinet(tg_id))
        assert cab == run(gw.cabinet(tg_id))
        # Round trip through JSON: the mock produces exactly what the bot would send.
        assert BotCabinet.model_validate_json(cab.model_dump_json()) == cab
        subs = {s.kind: s for s in cab.subscriptions}
        kinds |= set(subs)
        main = subs["main"]
        assert main.status == "active" and main.days_left > 0
        assert main.valid_until > datetime.now(UTC)
        assert main.sub_url.startswith("https://sub.example.com/")
        if "obhod" in subs:
            assert subs["obhod"].traffic.limit_bytes == 100 * GB
            assert subs["obhod"].traffic.reset == "month"
        assert 2 <= len(cab.devices) <= 4
        assert len({d.hwid for d in cab.devices}) == len(cab.devices)
        assert len(cab.traffic_daily) == 30
        dates = [d.date for d in cab.traffic_daily]
        assert dates == sorted(dates)
        assert 3 <= len(cab.payments) <= 6
        created = [p.created_at for p in cab.payments]
        assert created == sorted(created, reverse=True)
        ok = [p for p in cab.payments if p.status == "succeeded"]
        assert cab.stats.payments_count == len(ok)
        assert cab.stats.paid_total_rub == sum(p.amount_rub for p in ok)
        assert {n.name for n in cab.nodes} == NODES
        assert cab.traffic_by_node
    assert kinds == {"main", "obhod"}
    assert run(gw.cabinet(1)) != run(gw.cabinet(2))


def test_mock_delete_device():
    gw = MockGateway()
    cab = run(gw.cabinet(5))
    assert run(gw.delete_device(5, cab.devices[0].hwid)) is True
    assert run(gw.delete_device(5, "nope")) is False


def test_get_gateway_picks_by_config(monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "bot_api_url", "http://bot-internal-api:8001")
    monkeypatch.setattr(s, "remnawave_api_url", "")
    assert is_demo(get_gateway())
    monkeypatch.setattr(s, "remnawave_api_url", "http://panel:3000")
    gw = get_gateway()
    assert isinstance(gw, LiveGateway) and not is_demo(gw)
    assert get_gateway() is gw  # one shared pair of clients and caches
    # no bot API yet: still live, with a panel-only profile
    monkeypatch.setattr(s, "bot_api_url", "")
    assert not is_demo(get_gateway())


# ---------- bot profile client ----------


def test_bot_profile_ok_tolerant_and_token():
    bot = FakeBot()
    prof = run(make_bot(bot).profile(TG))
    assert prof.user.telegram_id == TG
    assert [a.panel_id for a in prof.accounts] == [MAIN_ID, OBHOD_ID]
    req = bot.calls[0]
    assert str(req.url) == f"http://bot:8001/internal/site/users/{TG}/profile"
    assert req.headers["X-Internal-Token"] == "tok-123"


def test_bot_profile_404_is_none_and_cached():
    bot = FakeBot((404, {"error": "not_found"}))
    client = make_bot(bot)
    assert run(client.profile(TG)) is None
    assert run(client.profile(TG)) is None
    assert len(bot.calls) == 1


@pytest.mark.parametrize(
    "answer",
    [
        (500, {"error": "boom"}),
        (403, {"error": "forbidden"}),
        (200, {"weird": True}),
        httpx.ReadTimeout("slow"),
        httpx.ConnectError("down"),
    ],
)
def test_bot_profile_unavailable(answer):
    with pytest.raises(GatewayUnavailable):
        run(make_bot(FakeBot(answer)).profile(TG))


def test_bot_cache_per_id_and_expiry():
    bot = FakeBot()
    client = make_bot(bot)
    run(client.profile(1))
    run(client.profile(1))
    run(client.profile(2))
    assert len(bot.calls) == 2
    client.drop_cache(1)
    run(client.profile(1))
    assert len(bot.calls) == 3
    fresh = make_bot(bot, cache_ttl=0)
    run(fresh.profile(1))
    run(fresh.profile(1))
    assert len(bot.calls) == 5


# ---------- panel client ----------


def test_panel_calls_match_contract():
    fp = FakePanel()
    pc = make_panel(fp)

    async def go():
        u = await pc.get_user(MAIN_ID)
        assert u.id == MAIN_ID and u.userTraffic.usedTrafficBytes == 5 * GB
        assert await pc.get_user(12345) is None
        devs = await pc.devices(MAIN_ID)
        assert devs[0].hwid == "own/hw 1" and not hasattr(devs[0], "requestIp")
        nodes = await pc.nodes()
        assert nodes[0].name == "nl-1" and "address" not in nodes[0].model_dump()
        usage = await pc.usage(MAIN_ID, datetime(2026, 9, 1).date(), datetime(2026, 9, 23).date())
        assert usage.series[0].name == "nl-1"
        found = await pc.find_user_by_telegram(TG)
        assert [x.id for x in found] == [MAIN_ID, OBHOD_ID]
        assert await pc.delete_device(MAIN_ID, "own/hw 1") is True
        await pc.aclose()

    run(go())
    by_path = {(r.method, r.url.path): r for r in fp.calls}
    assert all(r.headers["Authorization"] == "Bearer panel-tok" for r in fp.calls)
    assert ("GET", f"/api/users/{MAIN_ID}") in by_path  # base url "/api" suffix is not doubled
    assert ("GET", f"/api/hwid/devices/{MAIN_ID}") in by_path
    usage_req = by_path[("GET", f"/api/bandwidth-stats/users/{MAIN_ID}")]
    assert (
        usage_req.url.params["start"] == "2026-09-01"
        and usage_req.url.params["end"] == "2026-09-23"
    )
    lookup = by_path[("GET", "/api/users")]
    assert json.loads(lookup.url.params["filters"]) == [{"id": "telegramId", "value": str(TG)}]
    delete = by_path[("POST", "/api/hwid/devices/delete")]
    assert json.loads(delete.content) == {"userId": MAIN_ID, "hwid": "own/hw 1"}
    # only the allowlist was touched
    allowed = ("/api/users", "/api/hwid/devices/", "/api/bandwidth-stats/users/", "/api/nodes")
    assert all(r.url.path.startswith(allowed) for r in fp.calls)


@pytest.mark.parametrize("base", ["https://panel.example", "https://panel.example/api/"])
def test_panel_base_url_forms(base):
    fp = FakePanel()
    run(PanelClient(base, "t", transport=httpx.MockTransport(fp)).nodes())
    assert str(fp.calls[0].url) == "https://panel.example/api/nodes"


def test_panel_telegram_lookup_is_exact():
    fp = FakePanel()
    fp.users[OTHER_ID] = panel_user(OTHER_ID, tg=int(f"{TG}5"))  # LIKE would match 775
    found = run(make_panel(fp).find_user_by_telegram(TG))
    assert OTHER_ID not in [u.id for u in found]


def test_panel_cache_and_drop():
    fp = FakePanel()
    pc = make_panel(fp)

    async def go():
        await pc.get_user(MAIN_ID)
        await pc.get_user(MAIN_ID)
        await pc.devices(MAIN_ID)
        await pc.devices(MAIN_ID)
        assert len(fp.calls) == 2
        await pc.delete_device(MAIN_ID, "own/hw 1")
        await pc.devices(MAIN_ID)
        await pc.get_user(MAIN_ID)
        assert len(fp.calls) == 5  # both dropped after delete

    run(go())


@pytest.mark.parametrize("fail", [httpx.ReadTimeout("slow"), httpx.ConnectError("x"), 502, 401])
def test_panel_unavailable(fail):
    def handler(req):
        if isinstance(fail, Exception):
            raise fail
        return httpx.Response(fail)

    pc = PanelClient("http://panel", "t", transport=httpx.MockTransport(handler))
    with pytest.raises(PanelUnavailable):
        run(pc.get_user(1))


def test_rewrite_sub_url():
    base = "https://sub.crs-projects.com"
    assert (
        rewrite_sub_url("http://10.0.0.1:3010/abc?x=1", base)
        == "https://sub.crs-projects.com/abc?x=1"
    )
    assert (
        rewrite_sub_url("https://sub.crs-projects.com/abc", base)
        == "https://sub.crs-projects.com/abc"
    )
    assert (
        rewrite_sub_url("https://old.example/abc", "https://s.example/p/")
        == "https://s.example/p/abc"
    )
    assert rewrite_sub_url("https://old.example/abc", "") == "https://old.example/abc"


# ---------- live gateway ----------


def test_live_cabinet_composes_bot_and_panel(caplog):
    caplog.set_level("DEBUG")
    cab = run(make_live().cabinet(TG))
    assert cab.partial is False and cab.errors == []
    main, obhod = cab.subscriptions
    assert (main.kind, main.plan_code, main.status) == ("main", "standard", "active")
    assert main.sub_url == f"https://sub.example.com/secret{MAIN_ID}"
    assert main.days_left > 0 and main.is_lifetime is False
    assert main.traffic.limit_bytes is None and main.traffic.reset == "none"
    assert main.traffic.used_bytes == 5 * GB and main.last_node == "nl-1"
    assert obhod.traffic.limit_bytes == 100 * GB and obhod.traffic.reset == "month"
    assert obhod.package.code == "obhod_250"
    assert len(cab.traffic_daily) == 30
    assert cab.traffic_daily[-1].main_bytes == GB and cab.traffic_daily[-1].obhod_bytes == GB
    assert cab.traffic_daily[0].main_bytes == 0
    assert cab.traffic_by_node[0].node == "nl-1" and cab.traffic_by_node[0].country == "nl"
    assert cab.traffic_by_node[0].bytes_30d == 6 * GB  # 3 days x 2 accounts
    assert cab.devices[0].app == "Happ/3.1.0" and cab.devices[0].subscription == "main"
    assert [n.model_dump() for n in cab.nodes] == [
        {"name": "nl-1", "country": "nl", "online": True}
    ]
    dumped = cab.model_dump_json()
    assert "203.0.113.7" not in dumped and "198.51.100.10" not in dumped
    assert cab.payments[0].id == 481
    assert "secret" not in caplog.text and "panel-tok" not in caplog.text


def test_live_lifetime_and_statuses():
    fp = FakePanel()
    fp.users[MAIN_ID]["expireAt"] = "2099-12-31T00:00:00.000Z"
    fp.users[OBHOD_ID]["status"] = "LIMITED"
    main, obhod = run(make_live(panel=fp).cabinet(TG)).subscriptions
    assert main.is_lifetime and main.valid_until is None and main.days_left is None
    assert obhod.status == "limited"


def test_live_main_fallback_by_telegram():
    prof = json.loads(json.dumps(BOT_PROFILE))
    del prof["accounts"][0]["remna_uuid"]
    cab = run(make_live(bot=FakeBot((200, prof))).cabinet(TG))
    assert cab.subscriptions[0].sub_url.endswith(f"secret{MAIN_ID}")


def test_live_bot_404_and_down():
    assert run(make_live(bot=FakeBot((404, {}))).cabinet(TG)) is None
    with pytest.raises(GatewayUnavailable):
        run(make_live(bot=FakeBot(httpx.ConnectError("x"))).cabinet(TG))


def test_live_partial_when_panel_down():
    fp = FakePanel()
    fp.down = True
    cab = run(make_live(panel=fp).cabinet(TG))
    assert cab.partial is True and cab.errors == ["panel"]
    assert [s.status for s in cab.subscriptions] == ["unknown", "unknown"]
    assert all(s.sub_url is None for s in cab.subscriptions)
    assert cab.devices == [] and cab.nodes == [] and len(cab.traffic_daily) == 30
    assert cab.payments[0].id == 481  # bot data still there


def test_live_delete_checks_ownership():
    fp = FakePanel()
    gw = make_live(panel=fp)
    assert run(gw.delete_device(TG, "foreign")) is False  # belongs to panel user 999
    assert fp.deleted == []
    assert run(gw.delete_device(TG, "own/hw 1")) is True
    assert fp.deleted == [{"userId": MAIN_ID, "hwid": "own/hw 1"}]
    fp.down = True
    with pytest.raises(GatewayUnavailable):
        run(gw.delete_device(TG, "own/hw 1"))


# ---------- endpoints ----------


@pytest.fixture
def live_gw():
    """Swap the gateway for a LiveGateway over a fake bot and a fake panel."""

    def use(bot: FakeBot | None = None, panel: FakePanel | None = None) -> LiveGateway:
        gw = make_live(bot, panel)
        app.dependency_overrides[get_gateway] = lambda: gw
        return gw

    yield use
    app.dependency_overrides.pop(get_gateway, None)


def test_cabinet_requires_session(client):
    assert client.get("/api/cabinet").status_code == 401
    assert client.delete("/api/cabinet/devices/abc").status_code == 401


def test_cabinet_unlinked(client):
    register(client)
    assert client.get("/api/cabinet").json() == {"linked": False, "demo": True, "data": None}
    assert client.delete("/api/cabinet/devices/abc").status_code == 404


def test_cabinet_linked_mock(client):
    client.post("/api/auth/telegram", json=telegram_payload(1001))
    cab = client.get("/api/cabinet").json()
    assert cab["linked"] is True and cab["demo"] is True
    data = cab["data"]
    assert data["user"]["telegram_id"] == 1001
    assert set(data) >= {
        "generated_at",
        "partial",
        "errors",
        "user",
        "subscriptions",
        "devices",
        "traffic_daily",
        "traffic_by_node",
        "payments",
        "stats",
        "nodes",
    }
    assert data["subscriptions"][0]["sub_url"].startswith("https://sub.example.com/")


def test_cabinet_live(client, live_gw):
    bot = FakeBot()
    live_gw(bot)
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    cab = client.get("/api/cabinet").json()
    assert cab["linked"] is True and cab["demo"] is False
    assert cab["data"]["subscriptions"][1]["package"]["code"] == "obhod_250"
    assert "future_block" not in cab["data"]
    assert bot.calls[0].url.path == f"/internal/site/users/{TG}/profile"


def test_cabinet_live_partial(client, live_gw):
    fp = FakePanel()
    fp.down = True
    live_gw(panel=fp)
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    data = client.get("/api/cabinet").json()["data"]
    assert data["partial"] is True and data["errors"] == ["panel"]


def test_cabinet_bot_404(client, live_gw):
    live_gw(FakeBot((404, {"error": "not_found"})))
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    assert client.get("/api/cabinet").json() == {"linked": True, "demo": False, "data": None}


def test_cabinet_bot_down(client, live_gw):
    live_gw(FakeBot(httpx.ReadTimeout("slow")))
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    res = client.get("/api/cabinet")
    assert res.status_code == 503 and res.json()["error"] == "bot_unavailable"
    assert "ё" not in res.json()["message"]


def test_delete_device_endpoint(client, live_gw):
    fp = FakePanel()
    live_gw(panel=fp)
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    assert client.delete("/api/cabinet/devices/own%2Fhw%201").status_code == 204
    assert fp.deleted == [{"userId": MAIN_ID, "hwid": "own/hw 1"}]
    rows = run_sql("select meta from web.audit_log where event = 'device_delete'")
    assert json.loads(rows[0]["meta"]) == {"hwid": "own/hw", "ok": True}

    res = client.delete("/api/cabinet/devices/foreign")
    assert res.status_code == 404 and res.json()["error"] == "device_not_found"
    assert len(fp.deleted) == 1

    fp.down = True
    assert client.delete("/api/cabinet/devices/own%2Fhw%201").status_code == 503


def test_delete_device_needs_origin(client, live_gw):
    live_gw()
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    res = client.delete("/api/cabinet/devices/abc", headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
