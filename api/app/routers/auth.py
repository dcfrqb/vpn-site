from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from app import mailer, passkeys, telegram
from app.accounts import (
    MaybeAuth,
    account_json,
    audit,
    clear_session_cookie,
    consume_token,
    get_account,
    issue_token,
    peek_token,
    revoke_sessions,
    start_session,
)
from app.db import Conn
from app.errors import ApiError
from app.security import (
    check_password_policy,
    client_host,
    hash_password,
    limiter,
    needs_rehash,
    normalize_email,
    verify_password,
)

router = APIRouter(prefix="/auth")


class Credentials(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=1024)


class EmailIn(BaseModel):
    email: str = Field(max_length=320)


class TokenIn(BaseModel):
    token: str = Field(max_length=256)


class ResetIn(TokenIn):
    password: str = Field(max_length=1024)


class TelegramIn(BaseModel):
    # Extra widget fields must take part in the HMAC check, so they are kept.
    model_config = ConfigDict(extra="allow")
    id: int
    first_name: str = Field(max_length=256)
    last_name: str | None = Field(None, max_length=256)
    username: str | None = Field(None, max_length=64)
    photo_url: str | None = Field(None, max_length=1024)
    auth_date: int
    hash: str = Field(max_length=128)


class PasskeyLoginIn(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]


@router.post("/register", status_code=201)
async def register(body: Credentials, request: Request, response: Response, conn: Conn):
    limiter.hit("register", client_host(request))
    email = normalize_email(body.email)
    check_password_policy(body.password, email)
    pw_hash = await hash_password(body.password)
    try:
        acc = await conn.fetchrow(
            "insert into web.accounts (email, password_hash) values ($1, $2) returning *",
            email,
            pw_hash,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "email_taken") from None
    await audit(conn, request, "register", acc["id"])
    token = await issue_token(conn, acc["id"], "verify_email", email)
    await mailer.send(conn, email, mailer.VERIFY, mailer.verify_link(token))
    await start_session(conn, request, response, acc["id"], "password")
    return {"account": await account_json(conn, await get_account(conn, acc["id"]))}


@router.post("/email/check")
async def email_check(body: EmailIn, request: Request, conn: Conn):
    """First step of the single email form: sign in or create an account."""
    limiter.hit("email_check", client_host(request))
    email = normalize_email(body.email)
    acc = await conn.fetchrow("select password_hash from web.accounts where email = $1", email)
    return {"exists": acc is not None, "has_password": bool(acc and acc["password_hash"])}


@router.post("/login")
async def login(body: Credentials, request: Request, response: Response, conn: Conn):
    email = body.email.strip().lower()
    limiter.hit("login", client_host(request), f"email:{email}")
    acc = await conn.fetchrow("select * from web.accounts where email = $1", email)
    stored = acc["password_hash"] if acc else None
    if not await verify_password(stored, body.password):
        await audit(conn, request, "login_failed", acc["id"] if acc else None, method="password")
        raise ApiError(401, "invalid_credentials")
    if needs_rehash(stored):
        await conn.execute(
            "update web.accounts set password_hash = $2 where id = $1",
            acc["id"],
            await hash_password(body.password),
        )
    await start_session(conn, request, response, acc["id"], "password")
    return {"account": await account_json(conn, await get_account(conn, acc["id"]))}


@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, conn: Conn, auth: MaybeAuth) -> None:
    if auth:
        await conn.execute(
            "update web.sessions set revoked_at = now() where id_hash = $1", auth.sid
        )
        await audit(conn, request, "logout", auth.account_id)
    clear_session_cookie(response)


@router.post("/logout-all", status_code=204)
async def logout_all(request: Request, response: Response, conn: Conn, auth: MaybeAuth) -> None:
    if auth is None:
        raise ApiError(401, "unauthorized")
    await revoke_sessions(conn, auth.account_id)
    await audit(conn, request, "logout_all", auth.account_id)
    clear_session_cookie(response)


@router.post("/telegram")
async def telegram_login(
    body: TelegramIn, request: Request, response: Response, conn: Conn, auth: MaybeAuth
):
    telegram.verify_widget(body.model_dump(exclude_none=True))
    account_id = await telegram.apply_identity(
        conn, request, response, auth, body.id, body.username, body.first_name
    )
    return {"account": await account_json(conn, await get_account(conn, account_id))}


@router.post("/forgot")
async def forgot(body: EmailIn, request: Request, conn: Conn) -> dict:
    email = body.email.strip().lower()
    limiter.hit("forgot", client_host(request), f"email:{email}")
    acc = await conn.fetchrow("select id from web.accounts where email = $1", email)
    if acc:
        token = await issue_token(conn, acc["id"], "reset_password", email)
        await mailer.send(conn, email, mailer.RESET, mailer.reset_link(token))
        await audit(conn, request, "password_reset_requested", acc["id"])
    return {"ok": True}


@router.post("/reset", status_code=204)
async def reset(body: ResetIn, request: Request, conn: Conn) -> None:
    row = await peek_token(conn, body.token, "reset_password")
    check_password_policy(body.password, row["email"])
    pw_hash = await hash_password(body.password)
    async with conn.transaction():
        await consume_token(conn, body.token, "reset_password")
        # Following the emailed link proves the address, so it counts as verified.
        await conn.execute(
            "update web.accounts set password_hash = $2,"
            " email_verified_at = coalesce(email_verified_at, now()) where id = $1",
            row["account_id"],
            pw_hash,
        )
        await revoke_sessions(conn, row["account_id"])
        await audit(conn, request, "password_reset", row["account_id"])


@router.post("/verify-email", status_code=204)
async def verify_email(body: TokenIn, request: Request, conn: Conn) -> None:
    row = await consume_token(conn, body.token, "verify_email")
    await conn.execute(
        "update web.accounts set email_verified_at = now() where id = $1", row["account_id"]
    )
    await audit(conn, request, "email_verified", row["account_id"])


@router.post("/passkey/login/options")
async def passkey_login_options(request: Request, conn: Conn) -> dict:
    limiter.hit("passkey", client_host(request))
    return await passkeys.authentication_options(conn)


@router.post("/passkey/login/verify")
async def passkey_login_verify(
    body: PasskeyLoginIn, request: Request, response: Response, conn: Conn
):
    limiter.hit("passkey", client_host(request))
    try:
        account_id = await passkeys.verify_authentication(conn, body.challenge_id, body.credential)
    except ApiError:
        await audit(conn, request, "login_failed", method="passkey")
        raise
    await start_session(conn, request, response, account_id, "passkey")
    return {"account": await account_json(conn, await get_account(conn, account_id))}
