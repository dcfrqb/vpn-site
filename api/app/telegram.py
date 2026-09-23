"""Telegram Login Widget payload check (core.telegram.org/widgets/login#checking-authorization)."""

import hashlib
import hmac
import time
from uuid import UUID

from fastapi import Request, Response

from app.accounts import Auth, audit, start_session
from app.config import get_settings
from app.errors import ApiError

MAX_AGE = 24 * 60 * 60


def verify_widget(data: dict) -> None:
    token = get_settings().telegram_login_bot_token
    if not token:
        raise ApiError(503, "telegram_unavailable")
    fields = {k: v for k, v in data.items() if k != "hash" and v is not None}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(data.get("hash", ""))):
        raise ApiError(401, "telegram_invalid")
    age = time.time() - int(data["auth_date"])
    if age > MAX_AGE:
        raise ApiError(401, "telegram_expired")
    if age < -300:
        raise ApiError(401, "telegram_invalid")


async def apply_identity(
    conn,
    request: Request,
    response: Response,
    auth: Auth | None,
    tg_id: int,
    username: str | None,
    first_name: str | None,
) -> UUID:
    """Link telegram to the signed-in account, or sign in (creating the account if new)."""
    owner = await conn.fetchval("select id from web.accounts where telegram_id = $1", tg_id)

    if auth is not None:
        if owner is not None and owner != auth.account_id:
            raise ApiError(409, "telegram_taken")
        await conn.execute(
            "update web.accounts set telegram_id = $2, telegram_username = $3,"
            " telegram_first_name = $4 where id = $1",
            auth.account_id,
            tg_id,
            username,
            first_name,
        )
        if owner is None:
            await audit(conn, request, "telegram_link", auth.account_id, telegram_id=tg_id)
        return auth.account_id

    if owner is None:
        owner = await conn.fetchval(
            "insert into web.accounts (telegram_id, telegram_username, telegram_first_name)"
            " values ($1, $2, $3) on conflict (telegram_id) do update"
            " set telegram_username = excluded.telegram_username returning id",
            tg_id,
            username,
            first_name,
        )
        await audit(conn, request, "register", owner, method="telegram")
    else:
        await conn.execute(
            "update web.accounts set telegram_username = $2, telegram_first_name = $3"
            " where id = $1",
            owner,
            username,
            first_name,
        )
    await start_session(conn, request, response, owner, "telegram")
    return owner
