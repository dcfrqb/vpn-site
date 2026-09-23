"""DB tests need a real Postgres in TEST_DATABASE_URL; without it they are skipped.

Local: docker run -d --rm --name vpn-site-testdb -e POSTGRES_PASSWORD=test \
         -p 55432:5432 postgres:16-alpine
       TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/postgres uv run pytest
"""

import asyncio
import hashlib
import hmac
import os
import time

import asyncpg
import pytest
from fastapi.testclient import TestClient

from app import db
from app.config import get_settings
from app.main import app
from app.security import limiter

TEST_DB = os.environ.get("TEST_DATABASE_URL", "")
ORIGIN = "https://testserver"
BOT_TOKEN = "123456:TEST-TOKEN"
PASSWORD = "correct horse battery"


def run_sql(sql: str, *args, fetch: bool = True):
    async def go():
        conn = await asyncpg.connect(TEST_DB)
        try:
            return await conn.fetch(sql, *args) if fetch else await conn.execute(sql, *args)
        finally:
            await conn.close()

    return asyncio.run(go())


@pytest.fixture(scope="session")
def test_settings():
    if not TEST_DB:
        pytest.skip("TEST_DATABASE_URL is not set")
    run_sql("drop schema if exists web cascade", fetch=False)
    s = get_settings()
    saved = s.model_dump()
    s.database_url = TEST_DB
    s.public_origin = ORIGIN
    s.telegram_login_bot_token = BOT_TOKEN
    s.webauthn_rp_id = "testserver"
    s.smtp_host = ""
    yield s
    for k, v in saved.items():
        setattr(s, k, v)


@pytest.fixture
def client(test_settings):
    limiter.reset()
    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN}) as c:
        assert db.pool is not None
        tables = [
            r["tablename"]
            for r in run_sql("select tablename from pg_tables where schemaname = 'web'")
            if r["tablename"] != "schema_migrations"
        ]
        run_sql(f"truncate {', '.join('web.' + t for t in tables)} cascade", fetch=False)
        yield c


COOKIE = "__Host-sid"


def sid(c) -> str:
    return c.cookies.get(COOKIE)


def use_sid(c, value: str | None) -> None:
    """Switch the test client to another session, as if it were another browser."""
    c.cookies.clear()
    if value:
        c.cookies.set(COOKIE, value, domain="testserver.local", path="/")


def register(c, email="user@example.com", password=PASSWORD):
    return c.post("/api/auth/register", json={"email": email, "password": password})


def telegram_payload(tg_id=4242, auth_date=None, token=BOT_TOKEN, **extra):
    data = {
        "id": tg_id,
        "first_name": "Ivan",
        "username": f"ivan{tg_id}",
        "auth_date": int(auth_date if auth_date is not None else time.time()),
        **extra,
    }
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(token.encode()).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return data


def outbox_token(email: str) -> str:
    body = run_sql(
        "select body from web.outbox where to_email = $1 order by id desc limit 1", email
    )[0]["body"]
    return body.split("token=")[1].split()[0]
