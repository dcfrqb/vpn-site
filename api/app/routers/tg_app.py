"""Sign-in through the Telegram app (no phone number, no widget).

1. Browser: POST /auth/tg/start -> request id + t.me deep link, cookie binds the request to it.
2. User opens the link in @crs_vpn_bot; the bot relays to tg_bot_bridge, which marks the request.
3. Browser polls GET /auth/tg/status; on "confirmed" the api signs in or links telegram.
"""

import hashlib
import secrets
from datetime import timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app import telegram
from app.accounts import MaybeAuth, _user_agent, account_json, get_account
from app.config import get_settings
from app.db import Conn
from app.errors import ApiError
from app.security import client_host, client_ip, limiter

router = APIRouter(prefix="/auth/tg")

TTL = timedelta(minutes=5)
COOKIE = "tg_login"
COOKIE_PATH = "/api/auth/tg"


def _sha(value: str) -> bytes:
    return hashlib.sha256(value.encode()).digest()


class StartIn(BaseModel):
    mode: Literal["login", "link"] = "login"


@router.post("/start")
async def start(body: StartIn, request: Request, response: Response, conn: Conn, auth: MaybeAuth):
    settings = get_settings()
    if not (settings.site_internal_token and settings.telegram_bot_username):
        raise ApiError(503, "telegram_unavailable")
    limiter.hit("tg_start", client_host(request))
    if body.mode == "link" and auth is None:
        raise ApiError(401, "unauthorized")

    payload = "login_" + secrets.token_urlsafe(24)  # /start accepts up to 64 chars [A-Za-z0-9_-]
    browser = secrets.token_urlsafe(32)
    request_id = await conn.fetchval(
        "insert into web.tg_login_requests"
        " (start_hash, browser_hash, mode, account_id, ip, user_agent, expires_at)"
        " values ($1, $2, $3, $4, $5, $6, now() + $7::interval) returning id",
        _sha(payload),
        _sha(browser),
        body.mode,
        auth.account_id if (auth and body.mode == "link") else None,
        client_ip(request),
        _user_agent(request),
        TTL,
    )
    response.set_cookie(
        COOKIE,
        browser,
        max_age=int(TTL.total_seconds()),
        path=COOKIE_PATH,
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    bot = settings.telegram_bot_username
    return {
        "request_id": str(request_id),
        "link": f"https://t.me/{bot}?start={payload}",
        "app_link": f"tg://resolve?domain={bot}&start={payload}",
        "bot": bot,
        "expires_in": int(TTL.total_seconds()),
    }


@router.get("/status")
async def status(id: UUID, request: Request, response: Response, conn: Conn, auth: MaybeAuth):
    limiter.hit("tg_poll", client_host(request))
    browser = request.cookies.get(COOKIE)
    row = await conn.fetchrow(
        "select * from web.tg_login_requests where id = $1 and browser_hash = $2",
        id,
        _sha(browser or ""),
    )
    if row is None:
        raise ApiError(404, "not_found")
    if row["status"] == "denied":
        return {"status": "denied"}
    if row["status"] != "confirmed":
        expired = await conn.fetchval("select now() > $1", row["expires_at"])
        return {"status": "expired" if expired else "pending"}

    # One use: only the poll that flips confirmed -> consumed may sign in.
    taken = await conn.fetchval(
        "update web.tg_login_requests set status = 'consumed'"
        " where id = $1 and status = 'confirmed' and expires_at > now() returning id",
        id,
    )
    if taken is None:
        return {"status": "expired"}
    response.delete_cookie(COOKIE, path=COOKIE_PATH)

    link_auth = None
    if row["mode"] == "link":
        if auth is None or auth.account_id != row["account_id"]:
            raise ApiError(401, "unauthorized")
        link_auth = auth
    account_id = await telegram.apply_identity(
        conn,
        request,
        response,
        link_auth,
        row["telegram_id"],
        row["telegram_username"],
        row["telegram_first_name"],
    )
    return {
        "status": "ok",
        "account": await account_json(conn, await get_account(conn, account_id)),
    }
