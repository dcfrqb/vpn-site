import time
from uuid import UUID

from tests.conftest import (
    COOKIE,
    PASSWORD,
    outbox_token,
    register,
    run_sql,
    sid,
    telegram_payload,
    use_sid,
)

EMAIL = "user@example.com"


def test_register_login_logout(client):
    r = register(client, "User@Example.com")
    assert r.status_code == 201
    acc = r.json()["account"]
    assert acc["email"] == EMAIL
    assert acc["email_verified"] is False and acc["has_password"] is True
    set_cookie = r.headers["set-cookie"]
    for attr in (f"{COOKIE}=", "HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert attr.lower() in set_cookie.lower()
    assert client.get("/api/me").status_code == 200

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").json()["error"] == "unauthorized"

    r = client.post("/api/auth/login", json={"email": " USER@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json()["account"]["email"] == EMAIL
    events = [r["event"] for r in run_sql("select event from web.audit_log order by id")]
    assert events == ["register", "login", "logout", "login"]


def test_session_stored_hashed(client):
    register(client)
    token = sid(client)
    rows = run_sql("select id_hash from web.sessions")
    assert len(rows) == 1 and token.encode() not in rows[0]["id_hash"]


def test_register_validation(client):
    assert register(client, "not-an-email").json()["error"] == "invalid_email"
    assert register(client, password="short").json()["error"] == "weak_password"
    assert register(client, "longpassword@x.io", "longpassword@x.io").status_code == 400
    assert register(client).status_code == 201
    r = register(client)
    assert r.status_code == 409 and r.json()["error"] == "email_taken"
    r = client.post("/api/auth/register", json={"email": 1})
    assert r.status_code == 422 and r.json()["error"] == "invalid_request"


def test_wrong_password_is_uniform(client):
    register(client)
    use_sid(client, None)
    wrong = client.post("/api/auth/login", json={"email": EMAIL, "password": "x" * 12})
    missing = client.post("/api/auth/login", json={"email": "no@example.com", "password": "x" * 12})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()
    assert wrong.json()["error"] == "invalid_credentials"
    assert "ё" not in wrong.json()["message"]


def test_login_rate_limit(client):
    for _ in range(10):
        client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12})
    r = client.post("/api/auth/login", json={"email": "a@example.com", "password": "x" * 12})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited" and r.json()["retry_after"] > 0
    assert int(r.headers["retry-after"]) > 0


def test_origin_check(client):
    for origin in ("https://evil.example", ""):
        r = client.post("/api/auth/logout", headers={"Origin": origin})
        assert r.status_code == 403 and r.json()["error"] == "bad_origin"
    assert client.get("/api/plans", headers={"Origin": "https://evil.example"}).status_code == 200


def test_sessions_list_and_revoke(client):
    register(client)
    first = sid(client)
    use_sid(client, None)
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    second = sid(client)
    assert first != second

    sessions = client.get("/api/me/sessions").json()
    assert len(sessions) == 2
    assert {"id", "current", "created_at", "last_seen_at", "ip", "user_agent"} <= set(sessions[0])
    other = next(s for s in sessions if not s["current"])
    assert len(other["id"]) == 16
    assert client.delete(f"/api/me/sessions/{other['id']}").status_code == 204
    assert client.delete(f"/api/me/sessions/{other['id']}").status_code == 404
    assert client.delete("/api/me/sessions/zz").status_code == 404

    use_sid(client, first)
    assert client.get("/api/me").status_code == 401
    use_sid(client, second)
    assert client.get("/api/me").status_code == 200


def test_logout_all(client):
    register(client)
    first = sid(client)
    use_sid(client, None)
    client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert client.post("/api/auth/logout-all").status_code == 204
    assert client.get("/api/me").status_code == 401
    use_sid(client, first)
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/logout-all").status_code == 401


def test_password_change(client):
    register(client)
    new = "another long password"
    r = client.post("/api/me/password", json={"new_password": new})
    assert r.status_code == 400 and r.json()["error"] == "wrong_password"
    r = client.post("/api/me/password", json={"current_password": "nope", "new_password": new})
    assert r.json()["error"] == "wrong_password"
    r = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": "s"})
    assert r.json()["error"] == "weak_password"
    r = client.post("/api/me/password", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 204
    assert client.get("/api/me").status_code == 200  # current session survives
    use_sid(client, None)
    assert (
        client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code
        == 401
    )
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": new}).status_code == 200


def test_forgot_and_reset(client):
    register(client)
    use_sid(client, None)
    unknown = client.post("/api/auth/forgot", json={"email": "ghost@example.com"})
    assert unknown.status_code == 200
    r = client.post("/api/auth/forgot", json={"email": EMAIL})
    assert r.status_code == 200 and r.json() == unknown.json()

    body = run_sql("select body from web.outbox where subject = 'Сброс пароля'")
    assert len(body) == 1 and "https://testserver/reset?token=" in body[0]["body"]
    token = outbox_token(EMAIL)
    assert run_sql("select 1 from web.auth_tokens where token_hash = $1", token.encode()) == []

    r = client.post("/api/auth/reset", json={"token": token, "password": "short"})
    assert r.json()["error"] == "weak_password"
    new = "brand new password"
    assert client.post("/api/auth/reset", json={"token": token, "password": new}).status_code == 204
    r = client.post("/api/auth/reset", json={"token": token, "password": new})
    assert r.status_code == 400 and r.json()["error"] == "invalid_token"
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": new}).status_code == 200
    assert client.get("/api/me").json()["account"]["email_verified"] is True


def test_reset_revokes_sessions(client):
    register(client)
    old = sid(client)
    client.post("/api/auth/forgot", json={"email": EMAIL})
    client.post("/api/auth/reset", json={"token": outbox_token(EMAIL), "password": "x" * 12})
    use_sid(client, old)
    assert client.get("/api/me").status_code == 401


def test_forgot_rate_limit(client):
    for _ in range(3):
        assert client.post("/api/auth/forgot", json={"email": EMAIL}).status_code == 200
    assert client.post("/api/auth/forgot", json={"email": EMAIL}).status_code == 429


def test_verify_email(client):
    register(client)
    body = run_sql("select body from web.outbox where subject = 'Подтверди email'")[0]["body"]
    assert "https://testserver/verify?token=" in body
    token = outbox_token(EMAIL)
    assert client.post("/api/auth/verify-email", json={"token": "bogus"}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    assert client.get("/api/me").json()["account"]["email_verified"] is True
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_verify_token_bound_to_email(client):
    register(client)
    old_token = outbox_token(EMAIL)
    r = client.post("/api/me/email", json={"email": "new@example.com", "password": PASSWORD})
    assert r.status_code == 204
    assert client.post("/api/auth/verify-email", json={"token": old_token}).status_code == 400
    token = outbox_token("new@example.com")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 204
    me = client.get("/api/me").json()["account"]
    assert me["email"] == "new@example.com" and me["email_verified"] is True


def test_email_change_rules(client):
    register(client, "other@example.com")
    use_sid(client, None)
    register(client)
    r = client.post("/api/me/email", json={"email": "new@example.com"})
    assert r.json()["error"] == "wrong_password"
    r = client.post("/api/me/email", json={"email": "Other@example.com", "password": PASSWORD})
    assert r.status_code == 409 and r.json()["error"] == "email_taken"


def test_telegram_login_creates_account(client):
    r = client.post("/api/auth/telegram", json=telegram_payload(photo_url="https://t.me/i.jpg"))
    assert r.status_code == 200
    acc = r.json()["account"]
    assert acc["telegram"] == {"id": 4242, "username": "ivan4242", "first_name": "Ivan"}
    assert acc["email"] is None and acc["has_password"] is False
    use_sid(client, None)
    again = client.post("/api/auth/telegram", json=telegram_payload()).json()["account"]
    assert again["id"] == acc["id"]


def test_telegram_invalid_and_stale(client):
    bad = telegram_payload(token="999:OTHER")
    r = client.post("/api/auth/telegram", json=bad)
    assert r.status_code == 401 and r.json()["error"] == "telegram_invalid"
    tampered = telegram_payload()
    tampered["username"] = "someone_else"
    assert client.post("/api/auth/telegram", json=tampered).json()["error"] == "telegram_invalid"
    stale = telegram_payload(auth_date=time.time() - 25 * 3600)
    r = client.post("/api/auth/telegram", json=stale)
    assert r.status_code == 401 and r.json()["error"] == "telegram_expired"
    assert run_sql("select 1 from web.accounts") == []


def test_telegram_link_and_conflict(client):
    register(client)
    r = client.post("/api/auth/telegram", json=telegram_payload(777))
    assert r.status_code == 200
    acc = r.json()["account"]
    assert acc["email"] == EMAIL and acc["telegram"]["id"] == 777
    events = [r["event"] for r in run_sql("select event from web.audit_log")]
    assert "telegram_link" in events

    use_sid(client, None)
    register(client, "second@example.com")
    r = client.post("/api/auth/telegram", json=telegram_payload(777))
    assert r.status_code == 409 and r.json()["error"] == "telegram_taken"


def test_last_login_method_guard(client):
    client.post("/api/auth/telegram", json=telegram_payload(555))
    r = client.delete("/api/me/telegram")
    assert r.status_code == 409 and r.json()["error"] == "last_login_method"

    client.post("/api/me/email", json={"email": "tg@example.com"})
    client.post("/api/me/password", json={"new_password": PASSWORD})
    assert client.delete("/api/me/telegram").status_code == 204
    me = client.get("/api/me").json()["account"]
    assert me["telegram"] is None and me["has_password"] is True
    events = {r["event"] for r in run_sql("select event from web.audit_log")}
    assert {"telegram_unlink", "password_change", "email_change"} <= events


def test_passkey_delete_guard(client):
    tg = client.post("/api/auth/telegram", json=telegram_payload(556)).json()["account"]
    run_sql(
        "insert into web.webauthn_credentials (id, account_id, public_key, name)"
        " values ($1, $2, $3, 'test')",
        b"\x01\x02\x03",
        UUID(tg["id"]),
        b"key",
    )
    passkey_id = client.get("/api/me").json()["account"]["passkeys"][0]["id"]
    assert passkey_id == "AQID"
    assert client.delete("/api/me/telegram").status_code == 204  # passkey remains
    r = client.delete(f"/api/me/passkeys/{passkey_id}")
    assert r.status_code == 409 and r.json()["error"] == "last_login_method"
    assert client.delete("/api/me/passkeys/AAAA").status_code == 404


def test_me_shape(client):
    register(client)
    acc = client.get("/api/me").json()["account"]
    assert set(acc) == {
        "id",
        "email",
        "email_verified",
        "telegram",
        "has_password",
        "passkeys",
        "created_at",
    }
    assert acc["passkeys"] == [] and acc["telegram"] is None


def test_me_requires_session(client):
    r = client.get("/api/me")
    assert r.status_code == 401 and r.json() == {
        "error": "unauthorized",
        "message": "Нужно войти в аккаунт",
    }
    use_sid(client, "forged-token")
    assert client.get("/api/me").status_code == 401


def test_passkey_login_options_and_garbage(client):
    r = client.post("/api/auth/passkey/login/options")
    assert r.status_code == 200
    opts = r.json()
    assert opts["rpId"] == "testserver" and opts["challenge"] and opts["challenge_id"]
    assert opts.get("allowCredentials", []) == []

    garbage = {"id": "AAAA", "rawId": "AAAA", "type": "public-key", "response": {}}
    r = client.post(
        "/api/auth/passkey/login/verify",
        json={"challenge_id": opts["challenge_id"], "credential": garbage},
    )
    assert r.status_code == 401 and r.json()["error"] == "passkey_invalid"
    # the challenge is gone after one attempt
    assert run_sql("select 1 from web.webauthn_challenges") == []
    r = client.post(
        "/api/auth/passkey/login/verify",
        json={"challenge_id": opts["challenge_id"], "credential": {"x": 1}},
    )
    assert r.status_code == 401


def test_passkey_register_options_and_garbage(client):
    assert client.post("/api/me/passkeys/options").status_code == 401
    register(client)
    opts = client.post("/api/me/passkeys/options").json()
    assert opts["rp"] == {"name": "CRS VPN", "id": "testserver"}
    assert opts["authenticatorSelection"]["residentKey"] == "required"
    assert opts["user"]["name"] == EMAIL
    r = client.post(
        "/api/me/passkeys/verify",
        json={"challenge_id": opts["challenge_id"], "credential": {"id": "x", "response": {}}},
    )
    assert r.status_code == 400 and r.json()["error"] == "passkey_invalid"


def test_passkey_rate_limit(client):
    for _ in range(20):
        assert client.post("/api/auth/passkey/login/options").status_code == 200
    assert client.post("/api/auth/passkey/login/options").status_code == 429


def test_register_rate_limit(client):
    for i in range(5):
        register(client, f"u{i}@example.com")
    assert register(client, "u9@example.com").status_code == 429


def test_migrations_recorded(client):
    rows = run_sql("select version from web.schema_migrations")
    assert [r["version"] for r in rows] == ["0001_init"]


def test_email_check(client):
    r = client.post("/api/auth/email/check", json={"email": "New@Example.com"})
    assert r.json() == {"exists": False, "has_password": False}
    register(client)
    r = client.post("/api/auth/email/check", json={"email": " USER@example.com"})
    assert r.json() == {"exists": True, "has_password": True}
    assert client.post("/api/auth/email/check", json={"email": "nope"}).status_code == 400


def test_email_check_rate_limit(client):
    for _ in range(20):
        client.post("/api/auth/email/check", json={"email": "a@example.com"})
    r = client.post("/api/auth/email/check", json={"email": "a@example.com"})
    assert r.status_code == 429
