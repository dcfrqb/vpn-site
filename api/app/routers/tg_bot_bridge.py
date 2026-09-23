"""Internal endpoints for @crs_vpn_bot: it forwards `/start login_...` and button presses here.

Not reachable from the internet (nginx denies /api/internal/), the bot calls the api over
the docker network with X-Internal-Token. The site builds every text and button, so the bot
handler stays a thin relay.
"""

import hashlib
import hmac
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import Conn
from app.errors import ApiError

router = APIRouter(prefix="/internal/tg-login")
PREFIX = "sitelogin"


class TgUser(BaseModel):
    id: int
    username: str | None = Field(None, max_length=64)
    first_name: str | None = Field(None, max_length=256)


class ClaimIn(BaseModel):
    payload: str = Field(max_length=64)
    user: TgUser


class AnswerIn(BaseModel):
    data: str = Field(max_length=64)
    user_id: int


def _check_token(token: str | None) -> None:
    expected = get_settings().site_internal_token
    if not expected or not hmac.compare_digest(token or "", expected):
        raise ApiError(403, "forbidden")


def device(ua: str | None) -> str:
    ua = ua or ""
    systems = (("iPhone", "iphone"), ("iPad", "ipad"), ("Android", "android"),
               ("Mac OS X", "mac"), ("Windows", "windows"), ("Linux", "linux"))  # fmt: skip
    browsers = (("YaBrowser", "яндекс браузер"), ("Edg/", "edge"), ("Firefox", "firefox"),
                ("Chrome", "chrome"), ("Safari", "safari"))  # fmt: skip
    os_ = next((name for key, name in systems if key in ua), "неизвестное устройство")
    browser = next((name for key, name in browsers if key in ua), "браузер")
    return f"{browser}, {os_}"


STALE = {"text": "ссылка для входа устарела или уже использована. начни вход на сайте заново."}


@router.post("/claim")
async def claim(body: ClaimIn, conn: Conn, x_internal_token: str | None = Header(None)):
    _check_token(x_internal_token)
    row = await conn.fetchrow(
        "update web.tg_login_requests set status = 'claimed', telegram_id = $2,"
        " telegram_username = $3, telegram_first_name = $4"
        " where start_hash = $1 and status = 'pending' and expires_at > now()"
        " returning id, mode, ip, user_agent, created_at",
        hashlib.sha256(body.payload.encode()).digest(),
        body.user.id,
        body.user.username,
        body.user.first_name,
    )
    if row is None:
        return STALE
    site = get_settings().public_origin.removeprefix("https://")
    action = "привязать этот telegram к аккаунту" if row["mode"] == "link" else "войти"
    text = (
        f"{action} на {site}?\n\n"
        f"устройство: {device(row['user_agent'])}\n"
        f"ip: {row['ip'] or 'неизвестен'}\n"
        f"запрос создан в {row['created_at']:%H:%M} utc\n\n"
        "если ты сейчас ничего не делал на сайте, нажми «отмена»."
    )
    rid = row["id"]
    return {
        "text": text,
        "buttons": [
            {"text": "подтвердить", "data": f"{PREFIX}:ok:{rid}"},
            {"text": "отмена", "data": f"{PREFIX}:no:{rid}"},
        ],
    }


@router.post("/answer")
async def answer(body: AnswerIn, conn: Conn, x_internal_token: str | None = Header(None)):
    _check_token(x_internal_token)
    prefix, verb, rid = (body.data.split(":", 2) + ["", ""])[:3]
    new = {"ok": "confirmed", "no": "denied"}.get(verb) if prefix == PREFIX else None
    try:
        request_id = UUID(rid)
    except ValueError:
        new = None
    done = None
    if new:
        # Only the telegram user who opened the link may answer, and only once.
        done = await conn.fetchval(
            "update web.tg_login_requests set status = $3"
            " where id = $1 and telegram_id = $2 and status = 'claimed'"
            " and expires_at > now() returning status",
            request_id,
            body.user_id,
            new,
        )
    if done == "confirmed":
        return {"text": "готово. вернись в браузер, вход уже выполнен."}
    if done == "denied":
        return {"text": "вход отменен."}
    return {"text": "запрос устарел. начни вход на сайте заново."}
