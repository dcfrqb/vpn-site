from urllib.parse import parse_qs, urlparse

from app.routers.tg_bot_bridge import device
from tests.conftest import register, run_sql

TG_USER = {"id": 777001, "username": "tester", "first_name": "Test"}


def start(client, mode="login"):
    r = client.post("/api/auth/tg/start", json={"mode": mode})
    assert r.status_code == 200, r.text
    data = r.json()
    payload = parse_qs(urlparse(data["link"]).query)["start"][0]
    assert data["link"].startswith("https://t.me/test_login_bot?start=login_")
    return data["request_id"], payload


INTERNAL = {"X-Internal-Token": "internal-test-token"}


def bot_flow(client, payload: str, answer: str = "ok", user=TG_USER) -> list[dict]:
    """What @crs_vpn_bot does: relay /start and the button press to the bridge."""
    replies = []
    r = client.post(
        "/api/internal/tg-login/claim", json={"payload": payload, "user": user}, headers=INTERNAL
    )
    assert r.status_code == 200, r.text
    replies.append(r.json())
    buttons = r.json().get("buttons")
    if buttons:
        data = buttons[0 if answer == "ok" else 1]["data"]
        r = client.post(
            "/api/internal/tg-login/answer",
            json={"data": data, "user_id": user["id"]},
            headers=INTERNAL,
        )
        replies.append(r.json())
    return replies


def test_login_via_app_creates_account(client):
    rid, payload = start(client)
    assert client.get(f"/api/auth/tg/status?id={rid}").json() == {"status": "pending"}
    sent = bot_flow(client, payload)
    assert "войти" in sent[0]["text"]
    r = client.get(f"/api/auth/tg/status?id={rid}")
    body = r.json()
    assert body["status"] == "ok"
    assert body["account"]["telegram"]["id"] == TG_USER["id"]
    assert client.get("/api/me").status_code == 200
    # one use
    assert client.get(f"/api/auth/tg/status?id={rid}").status_code == 404


def test_other_browser_cannot_poll(client):
    rid, payload = start(client)
    bot_flow(client, payload)
    client.cookies.delete("tg_login", path="/api/auth/tg")
    client.cookies.set("tg_login", "stolen", path="/api/auth/tg")
    assert client.get(f"/api/auth/tg/status?id={rid}").status_code == 404


def test_denied(client):
    rid, payload = start(client)
    bot_flow(client, payload, answer="no")
    assert client.get(f"/api/auth/tg/status?id={rid}").json() == {"status": "denied"}


def test_payload_single_use_and_other_user(client):
    rid, payload = start(client)
    bot_flow(client, payload)
    sent = bot_flow(client, payload, user={"id": 999, "first_name": "Evil"})
    assert "устарела" in sent[0]["text"]


def test_expired(client):
    rid, payload = start(client)
    run_sql(
        "update web.tg_login_requests set expires_at = now() - interval '1 second'", fetch=False
    )
    sent = bot_flow(client, payload)
    assert "устарела" in sent[0]["text"]
    assert client.get(f"/api/auth/tg/status?id={rid}").json() == {"status": "expired"}


def test_link_mode(client):
    register(client)
    rid, payload = start(client, mode="link")
    bot_flow(client, payload)
    body = client.get(f"/api/auth/tg/status?id={rid}").json()
    assert body["status"] == "ok"
    assert body["account"]["email"] == "user@example.com"
    assert body["account"]["telegram"]["id"] == TG_USER["id"]


def test_link_mode_requires_session(client):
    assert client.post("/api/auth/tg/start", json={"mode": "link"}).status_code == 401


def test_device_label():
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit Version/19 Safari/605"
    assert device(ua) == "safari, iphone"


def test_bridge_requires_token(client):
    _, payload = start(client)
    r = client.post("/api/internal/tg-login/claim", json={"payload": payload, "user": TG_USER})
    assert r.status_code == 403
    r = client.post(
        "/api/internal/tg-login/claim",
        json={"payload": payload, "user": TG_USER},
        headers={"X-Internal-Token": "wrong"},
    )
    assert r.status_code == 403


def test_answer_by_other_user_ignored(client):
    rid, payload = start(client)
    claim = client.post(
        "/api/internal/tg-login/claim", json={"payload": payload, "user": TG_USER}, headers=INTERNAL
    ).json()
    data = claim["buttons"][0]["data"]
    r = client.post(
        "/api/internal/tg-login/answer", json={"data": data, "user_id": 999}, headers=INTERNAL
    )
    assert "устарел" in r.json()["text"]
    assert client.get(f"/api/auth/tg/status?id={rid}").json() == {"status": "pending"}
