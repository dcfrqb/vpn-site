"""Google login uses a real isolated Postgres; external Google tokens are mocked."""

import pytest

from app import google_identity
from app.errors import ApiError
from tests.conftest import PASSWORD, register, run_sql, sid, use_sid


@pytest.fixture
def google(client, monkeypatch, test_settings):
    old = test_settings.google_client_id
    test_settings.google_client_id = "test.apps.googleusercontent.com"
    identity = {"sub": "google-123", "email": "new@gmail.com", "authoritative": True}

    async def verify(token, client_id, nonce):
        if token != "valid":
            raise ApiError(401, "google_invalid")
        return identity

    monkeypatch.setattr(google_identity, "verify", verify)
    yield identity
    test_settings.google_client_id = old


def login(client):
    assert client.post("/api/auth/google/options", json={}).status_code == 200
    return client.post("/api/auth/google", json={"credential": "valid"})


def test_disabled(client, test_settings):
    assert client.get("/api/auth/google/config").json() == {"enabled": False}
    assert client.post("/api/auth/google/options", json={}).status_code == 503
    assert client.post("/api/auth/google", json={"credential": "x"}).status_code == 503


def test_register_repeat_and_last_method(client, google):
    r = login(client)
    assert r.status_code == 200
    account = r.json()["account"]
    assert account["google"] == "new@gmail.com"
    assert account["email_verified"] is True
    assert account["has_password"] is False
    assert sid(client)
    assert client.delete("/api/me/google").status_code == 409
    client.post("/api/auth/logout")
    assert login(client).json()["account"]["id"] == account["id"]
    assert len(run_sql("select * from web.accounts")) == 1


def test_existing_email_requires_link(client, google):
    acc = register(client, "new@gmail.com").json()["account"]
    client.post("/api/auth/logout")
    assert login(client).json()["error"] == "google_link_required"
    assert client.get("/api/me").status_code == 401
    client.post("/api/auth/login", json={"email": "new@gmail.com", "password": PASSWORD})
    assert login(client).json()["account"]["id"] == acc["id"]
    assert client.delete("/api/me/google").status_code == 204
    assert client.get("/api/me").json()["account"]["google"] is None


def test_google_taken_and_session_bound_challenge(client, google):
    login(client)
    client.post("/api/auth/logout")
    register(client, "other@example.com")
    assert login(client).json()["error"] == "google_taken"
    assert client.get("/api/me").json()["account"]["google"] is None
    client.post("/api/auth/google/options", json={})
    # A change of session/account cannot turn a linking challenge into a login.
    use_sid(client, None)
    assert client.post("/api/auth/google", json={"credential": "valid"}).status_code == 401


def test_replay_expiry_bad_token_and_origin(client, google):
    client.post("/api/auth/google/options", json={})
    nonce = client.cookies.get("__Host-google-nonce")
    assert client.post("/api/auth/google", json={"credential": "bad"}).status_code == 401
    assert client.post("/api/auth/google", json={"credential": "valid"}).status_code == 200
    client.post("/api/auth/logout")
    client.cookies.set("__Host-google-nonce", nonce, domain="testserver.local", path="/")
    assert client.post("/api/auth/google", json={"credential": "valid"}).status_code == 401
    client.post("/api/auth/google/options", json={})
    run_sql(
        "update web.google_challenges set expires_at = now() - interval '1 second'", fetch=False
    )
    assert client.post("/api/auth/google", json={"credential": "valid"}).status_code == 401
    assert (
        client.post(
            "/api/auth/google/options", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )


def test_third_party_email_not_verified(client, google):
    google.update(email="new@example.com", authoritative=False)
    assert login(client).json()["account"]["email_verified"] is False


def test_google_is_alternative_login(client, google):
    from tests.conftest import telegram_payload

    client.post("/api/auth/telegram", json=telegram_payload())
    login(client)
    assert client.delete("/api/me/telegram").status_code == 204
    assert client.delete("/api/me/google").status_code == 409


@pytest.mark.parametrize(
    "changes", [{"nonce": "wrong"}, {"sub": ""}, {"email_verified": False}, {"email": "bad"}]
)
def test_claims_rejected(monkeypatch, changes):
    import asyncio

    claims = {
        "sub": "123",
        "email": "a@gmail.com",
        "email_verified": True,
        "nonce": "expected",
        **changes,
    }
    monkeypatch.setattr(google_identity, "_verify", lambda *_: claims)
    with pytest.raises(ApiError) as exc:
        asyncio.run(google_identity.verify("token", "client", "expected"))
    assert exc.value.code == "google_invalid"


def test_claims_verified(monkeypatch):
    import asyncio

    claims = {"sub": "123", "email": "a@gmail.com", "email_verified": True, "nonce": "expected"}
    monkeypatch.setattr(google_identity, "_verify", lambda *_: claims)
    assert asyncio.run(google_identity.verify("token", "client", "expected"))["authoritative"]


def test_invalid_signature_and_transport(monkeypatch):
    import asyncio

    from google.auth.exceptions import TransportError

    for error, code in [
        (ValueError("bad signature"), "google_invalid"),
        (TransportError("offline"), "google_unavailable"),
    ]:

        def fail(*_, err=error):
            raise err

        monkeypatch.setattr(google_identity, "_verify", fail)
        with pytest.raises(ApiError) as exc:
            asyncio.run(google_identity.verify("token", "client", "nonce"))
        assert exc.value.code == code


def test_real_signature_audience_issuer_and_expiry(monkeypatch):
    import asyncio
    import json
    import time

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth import crypt, jwt

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = (
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    signer = crypt.RSASigner.from_string(pem, key_id="test-key")

    class Transport:
        session = type("Session", (), {"close": lambda self: None})()

        def __call__(self, *args, **kwargs):
            return type(
                "Response", (), {"status": 200, "data": json.dumps({"test-key": public}).encode()}
            )()

    monkeypatch.setattr(google_identity, "Request", Transport)
    now = int(time.time())
    claims = {
        "sub": "123",
        "email": "a@gmail.com",
        "email_verified": True,
        "nonce": "nonce",
        "aud": "our-client",
        "iss": "https://accounts.google.com",
        "iat": now,
        "exp": now + 300,
    }
    token = jwt.encode(signer, claims).decode()
    assert asyncio.run(google_identity.verify(token, "our-client", "nonce"))["sub"] == "123"
    for changes in [
        {"aud": "other-client"},
        {"iss": "https://evil.test"},
        {"iat": now - 600, "exp": now - 300},
    ]:
        bad = jwt.encode(signer, {**claims, **changes}).decode()
        with pytest.raises(ApiError):
            asyncio.run(google_identity.verify(bad, "our-client", "nonce"))
    parts = token.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    with pytest.raises(ApiError):
        asyncio.run(google_identity.verify(".".join(parts), "our-client", "nonce"))
