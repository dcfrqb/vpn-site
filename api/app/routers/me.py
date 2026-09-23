from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field
from webauthn.helpers import base64url_to_bytes

from app import mailer, passkeys
from app.accounts import (
    CurrentAuth,
    account_json,
    audit,
    clear_session_cookie,
    ensure_other_login_method,
    issue_token,
    passkey_json,
    revoke_sessions,
)
from app.db import Conn
from app.errors import ApiError
from app.security import (
    check_password_policy,
    hash_password,
    normalize_email,
    verify_password,
)

router = APIRouter(prefix="/me")

_SESSION_ID_BYTES = 8  # public session id = hex of the first bytes of the token hash


class PasswordIn(BaseModel):
    current_password: str | None = Field(None, max_length=1024)
    new_password: str = Field(max_length=1024)


class EmailChangeIn(BaseModel):
    email: str = Field(max_length=320)
    password: str | None = Field(None, max_length=1024)


class PasskeyVerifyIn(BaseModel):
    challenge_id: UUID
    credential: dict[str, Any]
    name: str | None = Field(None, max_length=64)


async def _require_current_password(acc, password: str | None) -> None:
    if acc["password_hash"] is not None and not await verify_password(
        acc["password_hash"], password or ""
    ):
        raise ApiError(400, "wrong_password")


@router.get("")
async def me(auth: CurrentAuth, conn: Conn) -> dict:
    return {"account": await account_json(conn, auth.account)}


@router.post("/password", status_code=204)
async def change_password(body: PasswordIn, auth: CurrentAuth, request: Request, conn: Conn):
    acc = auth.account
    await _require_current_password(acc, body.current_password)
    check_password_policy(body.new_password, acc["email"])
    await conn.execute(
        "update web.accounts set password_hash = $2 where id = $1",
        acc["id"],
        await hash_password(body.new_password),
    )
    await revoke_sessions(conn, acc["id"], keep=auth.sid)
    await audit(conn, request, "password_change", acc["id"])


@router.post("/email", status_code=204)
async def change_email(body: EmailChangeIn, auth: CurrentAuth, request: Request, conn: Conn):
    acc = auth.account
    await _require_current_password(acc, body.password)
    email = normalize_email(body.email)
    try:
        await conn.execute(
            "update web.accounts set email = $2, email_verified_at = null where id = $1",
            acc["id"],
            email,
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "email_taken") from None
    token = await issue_token(conn, acc["id"], "verify_email", email)
    await mailer.send(conn, email, mailer.VERIFY, mailer.verify_link(token))
    await audit(conn, request, "email_change", acc["id"], old=acc["email"], new=email)


@router.delete("/telegram", status_code=204)
async def unlink_telegram(auth: CurrentAuth, request: Request, conn: Conn):
    acc = auth.account
    if acc["telegram_id"] is None:
        return
    await ensure_other_login_method(conn, acc, "telegram")
    await conn.execute(
        "update web.accounts set telegram_id = null, telegram_username = null,"
        " telegram_first_name = null where id = $1",
        acc["id"],
    )
    await audit(conn, request, "telegram_unlink", acc["id"], telegram_id=acc["telegram_id"])


@router.post("/passkeys/options")
async def passkey_options(auth: CurrentAuth, conn: Conn) -> dict:
    return await passkeys.registration_options(conn, auth.account)


@router.post("/passkeys/verify", status_code=201)
async def passkey_verify(body: PasskeyVerifyIn, auth: CurrentAuth, request: Request, conn: Conn):
    cred = await passkeys.verify_registration(
        conn, auth.account_id, body.challenge_id, body.credential
    )
    try:
        row = await conn.fetchrow(
            "insert into web.webauthn_credentials"
            " (id, account_id, public_key, sign_count, transports, name)"
            " values ($1, $2, $3, $4, $5, $6) returning *",
            cred["id"],
            auth.account_id,
            cred["public_key"],
            cred["sign_count"],
            cred["transports"],
            (body.name or "").strip() or "Паскей",
        )
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "passkey_exists") from None
    await audit(conn, request, "passkey_add", auth.account_id, name=row["name"])
    return passkey_json(row)


@router.delete("/passkeys/{passkey_id}", status_code=204)
async def passkey_delete(passkey_id: str, auth: CurrentAuth, request: Request, conn: Conn):
    try:
        raw = base64url_to_bytes(passkey_id)
    except ValueError:
        raise ApiError(404, "not_found") from None
    name = await conn.fetchval(
        "select name from web.webauthn_credentials where id = $1 and account_id = $2",
        raw,
        auth.account_id,
    )
    if name is None:
        raise ApiError(404, "not_found")
    await ensure_other_login_method(conn, auth.account, "passkey")
    await conn.execute("delete from web.webauthn_credentials where id = $1", raw)
    await audit(conn, request, "passkey_remove", auth.account_id, name=name)


@router.get("/sessions")
async def sessions(auth: CurrentAuth, conn: Conn) -> list[dict]:
    rows = await conn.fetch(
        "select id_hash, created_at, last_seen_at, host(ip) as ip, user_agent from web.sessions"
        " where account_id = $1 and revoked_at is null and expires_at > now()"
        " order by last_seen_at desc",
        auth.account_id,
    )
    return [
        {
            "id": r["id_hash"][:_SESSION_ID_BYTES].hex(),
            "current": r["id_hash"] == auth.sid,
            "created_at": r["created_at"],
            "last_seen_at": r["last_seen_at"],
            "ip": r["ip"],
            "user_agent": r["user_agent"],
        }
        for r in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: str, auth: CurrentAuth, request: Request, response: Response, conn: Conn
):
    try:
        prefix = bytes.fromhex(session_id)
    except ValueError:
        raise ApiError(404, "not_found") from None
    if len(prefix) != _SESSION_ID_BYTES:
        raise ApiError(404, "not_found")
    sid = await conn.fetchval(
        "update web.sessions set revoked_at = now() where account_id = $1"
        " and substring(id_hash from 1 for $3) = $2 and revoked_at is null returning id_hash",
        auth.account_id,
        prefix,
        _SESSION_ID_BYTES,
    )
    if sid is None:
        raise ApiError(404, "not_found")
    await audit(conn, request, "session_revoke", auth.account_id)
    if sid == auth.sid:
        clear_session_cookie(response)
