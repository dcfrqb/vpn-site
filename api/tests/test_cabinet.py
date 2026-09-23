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


def panel_usage(days=3, start=None, end=None):
    """Every day of [start, end] (default: the last `days` days), 1 GB on the last `days`."""
    from datetime import date, timedelta

    from app.gateway.live import MSK

    today = datetime.now(UTC).astimezone(MSK).date()
    end = date.fromisoformat(end) if end else today
    start = date.fromisoformat(start) if start else end - timedelta(days=days - 1)
    n = (end - start).days + 1
    cats = [(start + timedelta(days=i)).isoformat() for i in range(n)]
    data = [GB if (end - start).days - i < days else 0 for i in range(n)]
    return {
        "categories": cats,
        "sparklineData": data,
        "topNodes": [],
        "series": [
            {
                "uuid": NODE_UUID,
                "name": "remnanode-nl-1",
                "color": "#fff",
                "countryCode": "NL",
                "total": sum(data),
                "data": data,
            }
        ],
    }


PANEL_NODE = {
    "uuid": NODE_UUID,
    "id": 1,
    "name": "Remnanode-nl-1",
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
        self.usage_ranges: list[tuple[str, str]] = []

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
            self.usage_ranges.append((req.url.params["start"], req.url.params["end"]))
            return ok(panel_usage(start=req.url.params["start"], end=req.url.params["end"]))
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
        assert nodes[0].name == "Remnanode-nl-1" and "address" not in nodes[0].model_dump()
        usage = await pc.usage(MAIN_ID, datetime(2026, 9, 1).date(), datetime(2026, 9, 23).date())
        assert usage.series[0].name == "remnanode-nl-1"
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


# ---------- node names, monthly traffic, lifetime, demo scenarios ----------


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        ("remnanode-nl-2", "nl-2"),
        ("RemnaNode-fr", "fr"),
        ("remnanode-ru-1", "ru-1"),
        ("usa", "usa"),
        ("nl-remnanode-1", "nl-remnanode-1"),
        ("remnanode-", "remnanode-"),
    ],
)
def test_node_label(raw, label):
    from app.gateway.live import node_label

    assert node_label(raw) == label


def test_monthly_aggregation():
    from datetime import date

    from app.gateway.live import monthly
    from app.panel import PanelUsage

    today = date(2026, 9, 23)
    main = PanelUsage(
        categories=["2026-05-31", "2026-06-01", "2026-06-15", "2026-08-02", "2026-09-23"],
        sparklineData=[0, GB, 2 * GB, 3 * GB, 4 * GB],
    )
    obhod = PanelUsage(categories=["2026-09-01", "2026-09-02"], sparklineData=[GB, GB])
    out = monthly({"main": main, "obhod": obhod}, today)
    # starts at the first month with traffic (may has only a zero), gaps are zeros
    assert [m.month for m in out] == ["2026-06", "2026-07", "2026-08", "2026-09"]
    assert [m.main_bytes for m in out] == [3 * GB, 0, 3 * GB, 4 * GB]
    assert [m.obhod_bytes for m in out] == [0, 0, 0, 2 * GB]
    assert monthly({"main": PanelUsage()}, today) == []

    # never more than 24 months, the current one included
    old = PanelUsage(categories=["2023-01-10", "2026-09-01"], sparklineData=[GB, GB])
    out = monthly({"main": old}, today)
    assert len(out) == 24 and out[0].month == "2024-10" and out[-1].month == "2026-09"

    # across a year boundary
    jan = PanelUsage(categories=["2025-12-31", "2026-01-01"], sparklineData=[GB, GB])
    out = monthly({"main": jan}, date(2026, 1, 5))
    assert [m.month for m in out] == ["2025-12", "2026-01"]


def test_live_monthly_and_lifetime():
    from app.gateway.live import MSK, month_start

    fp = FakePanel()
    fp.users[OBHOD_ID]["createdAt"] = "2020-01-01T00:00:00.000Z"  # older than 24 months
    gw = make_live(panel=fp)
    today = datetime.now(UTC).astimezone(MSK).date()

    async def go():
        first = await gw.cabinet(TG)
        second = await gw.cabinet(TG)
        return first, second

    cab, _ = run(go())
    assert cab.partial is False
    months = cab.traffic_monthly
    assert months[-1].month == today.strftime("%Y-%m")
    assert sum(m.main_bytes for m in months) == 3 * GB
    assert sum(m.obhod_bytes for m in months) == 3 * GB
    main, obhod = cab.subscriptions
    assert main.traffic.lifetime_used_bytes == 50 * GB
    # one long call per user: from createdAt (MSK), or 24 months back at most
    long_ranges = {
        ("2025-12-01", today.isoformat()),
        (month_start(today, 23).isoformat(), today.isoformat()),
    }
    assert long_ranges <= set(fp.usage_ranges)
    # the long range is cached: the second cabinet did not ask again
    assert sum(1 for r in fp.usage_ranges if r in long_ranges) == 2


def test_live_monthly_slow_is_skipped_then_cached(monkeypatch):
    import app.gateway.live as live_mod

    monkeypatch.setattr(live_mod, "MONTHLY_WAIT", 0.05)
    fp = FakePanel()
    today = datetime.now(UTC).astimezone(live_mod.MSK).date()
    from datetime import timedelta

    cut = (today - timedelta(days=40)).isoformat()

    async def handler(req):
        start = req.url.params.get("start", "")
        if req.url.path.startswith("/api/bandwidth-stats/") and start < cut:
            await asyncio.sleep(0.2)  # the long range is slow
        return fp(req)

    gw = LiveGateway(
        make_bot(FakeBot()),
        PanelClient("http://panel", "t", transport=httpx.MockTransport(handler)),
        "https://sub.example.com",
    )

    async def go():
        first = await gw.cabinet(TG)
        await asyncio.sleep(0.3)  # the background load finishes and fills the cache
        second = await gw.cabinet(TG)
        return first, second

    first, second = run(go())
    assert first.traffic_monthly == [] and first.partial is False
    assert second.traffic_monthly and second.traffic_monthly[-1].month == today.strftime("%Y-%m")


def test_live_node_names_stripped():
    cab = run(make_live().cabinet(TG))
    assert cab.nodes[0].name == "nl-1"
    assert cab.traffic_by_node[0].node == "nl-1"
    assert cab.subscriptions[0].last_node == "nl-1"
    assert "remnanode" not in cab.model_dump_json().lower()


@pytest.mark.parametrize(
    ("scenario", "days", "status", "kinds"),
    [
        ("active", 35, "active", ["main", "obhod"]),
        ("expiring", 3, "active", ["main", "obhod"]),
        ("expired", 0, "expired", ["main"]),
        ("none", None, None, []),
    ],
)
def test_mock_scenarios(scenario, days, status, kinds):
    for tg_id in (1, 2, 3):
        cab = run(MockGateway().cabinet(tg_id, scenario=scenario))
        assert [s.kind for s in cab.subscriptions] == kinds
        if kinds:
            main = cab.subscriptions[0]
            assert (main.days_left, main.status, main.is_lifetime) == (days, status, False)
            assert cab.traffic_monthly and main.traffic.lifetime_used_bytes > 0
        else:
            assert cab.devices == [] and cab.traffic_monthly == [] and cab.payments == []
        if scenario == "expired":
            assert cab.subscriptions[0].valid_until < datetime.now(UTC)


def test_mock_monthly_shape():
    cab = run(MockGateway().cabinet(9))
    months = [m.month for m in cab.traffic_monthly]
    assert months == sorted(months) and 6 <= len(months) <= 24
    assert cab.traffic_monthly[-1].main_bytes == sum(
        d.main_bytes for d in cab.traffic_daily if d.date.strftime("%Y-%m") == months[-1]
    )


def test_cabinet_demo_scenarios(client, live_gw):
    assert client.get("/api/cabinet?demo=expiring").status_code == 401
    live_gw()  # even on the live gateway the preview is mock data
    client.post("/api/auth/telegram", json=telegram_payload(TG))
    res = client.get("/api/cabinet?demo=expiring").json()
    assert res["linked"] is True and res["demo"] is True
    assert res["data"]["subscriptions"][0]["days_left"] == 3
    assert "sub.example.com/demo-" in res["data"]["subscriptions"][0]["sub_url"]
    assert client.get("/api/cabinet?demo=none").json()["data"]["subscriptions"] == []
    assert (
        client.get("/api/cabinet?demo=expired").json()["data"]["subscriptions"][0]["status"]
        == "expired"
    )
    assert client.get("/api/cabinet?demo=lifetime-hack").status_code == 400
    assert client.get("/api/cabinet").json()["demo"] is False


def test_cabinet_demo_without_telegram(client):
    register(client)
    res = client.get("/api/cabinet?demo=active").json()
    assert res["demo"] is True and res["data"]["subscriptions"][0]["days_left"] == 35
