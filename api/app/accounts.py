"""Accounts, sessions, one-time tokens and the audit log."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends, Request, Response
from webauthn.helpers import bytes_to_base64url

from app.config import get_settings
from app.db import Conn
from app.errors import ApiError
from app.security import client_ip, hash_token, new_token

SESSION_TTL = timedelta(days=30)
_SLIDE_EVERY = timedelta(minutes=10)
TOKEN_TTL = {"verify_email": timedelta(hours=24), "reset_password": timedelta(hours=1)}


@dataclass
class Auth:
    sid: bytes
    account: asyncpg.Record

    @property
    def account_id(self) -> UUID:
        return self.account["id"]


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:512] if ua else None


async def audit(conn, request: Request, event: str, account_id=None, **meta) -> None:
    await conn.execute(
        "insert into web.audit_log (account_id, event, ip, user_agent, meta)"
        " values ($1, $2, $3, $4, $5)",
        account_id,
        event,
        client_ip(request),
        _user_agent(request),
        meta,
    )


def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.session_cookie,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
        secure=s.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.session_cookie, path="/", secure=s.cookie_secure, httponly=True, samesite="lax"
    )


async def optional_auth(request: Request, response: Response, conn: Conn) -> Auth | None:
    token = request.cookies.get(get_settings().session_cookie)
    if not token:
        return None
    sid = hash_token(token)
    row = await conn.fetchrow(
        "select a.*, s.last_seen_at as session_last_seen from web.sessions s"
        " join web.accounts a on a.id = s.account_id"
        " where s.id_hash = $1 and s.revoked_at is null and s.expires_at > now()",
        sid,
    )
    if row is None:
        return None
    if datetime.now(UTC) - row["session_last_seen"] > _SLIDE_EVERY:
        await conn.execute(
            "update web.sessions set last_seen_at = now(), expires_at = now() + $2::interval"
            " where id_hash = $1",
            sid,
            SESSION_TTL,
        )
        set_session_cookie(response, token)
    return Auth(sid, row)


async def require_auth(auth: Annotated[Auth | None, Depends(optional_auth)]) -> Auth:
    if auth is None:
        raise ApiError(401, "unauthorized")
    return auth


MaybeAuth = Annotated[Auth | None, Depends(optional_auth)]
CurrentAuth = Annotated[Auth, Depends(require_auth)]


async def start_session(
    conn, request: Request, response: Response, account_id: UUID, method: str
) -> None:
    """New session on every login; the session this browser had before is revoked."""
    old = request.cookies.get(get_settings().session_cookie)
    if old:
        await conn.execute(
            "update web.sessions set revoked_at = now() where id_hash = $1 and revoked_at is null",
            hash_token(old),
        )
    token, sid = new_token()
    await conn.execute(
        "insert into web.sessions (id_hash, account_id, expires_at, ip, user_agent)"
        " values ($1, $2, now() + $3::interval, $4, $5)",
        sid,
        account_id,
        SESSION_TTL,
        client_ip(request),
        _user_agent(request),
    )
    await conn.execute("update web.accounts set last_login_at = now() where id = $1", account_id)
    await audit(conn, request, "login", account_id, method=method)
    set_session_cookie(response, token)


async def revoke_sessions(conn, account_id: UUID, *, keep: bytes | None = None) -> None:
    await conn.execute(
        "update web.sessions set revoked_at = now()"
        " where account_id = $1 and revoked_at is null and id_hash is distinct from $2",
        account_id,
        keep,
    )


async def get_account(conn, account_id: UUID) -> asyncpg.Record:
    return await conn.fetchrow("select * from web.accounts where id = $1", account_id)


async def account_json(conn, acc: asyncpg.Record) -> dict:
    keys = await conn.fetch(
        "select id, name, created_at, last_used_at from web.webauthn_credentials"
        " where account_id = $1 order by created_at",
        acc["id"],
    )
    tg = None
    if acc["telegram_id"] is not None:
        tg = {
            "id": acc["telegram_id"],
            "username": acc["telegram_username"],
            "first_name": acc["telegram_first_name"],
        }
    return {
        "id": str(acc["id"]),
        "email": acc["email"],
        "email_verified": acc["email_verified_at"] is not None,
        "telegram": tg,
        "has_password": acc["password_hash"] is not None,
        "passkeys": [passkey_json(k) for k in keys],
        "created_at": acc["created_at"],
    }


def passkey_json(row) -> dict:
    return {
        "id": bytes_to_base64url(row["id"]),
        "name": row["name"],
        "created_at": row["created_at"],
        "last_used_at": row["last_used_at"],
    }


async def ensure_other_login_method(conn, acc: asyncpg.Record, removing: str) -> None:
    """409 if removing telegram or one passkey would leave the account without a way in."""
    passkeys = await conn.fetchval(
        "select count(*) from web.webauthn_credentials where account_id = $1", acc["id"]
    )
    left = [
        acc["email"] is not None and acc["password_hash"] is not None,
        acc["telegram_id"] is not None and removing != "telegram",
        passkeys - (removing == "passkey") > 0,
    ]
    if not any(left):
        raise ApiError(409, "last_login_method")


async def issue_token(conn, account_id: UUID, kind: str, email: str) -> str:
    token, token_hash = new_token()
    await conn.execute(
        "insert into web.auth_tokens (token_hash, account_id, kind, email, expires_at)"
        " values ($1, $2, $3, $4, now() + $5::interval)",
        token_hash,
        account_id,
        kind,
        email,
        TOKEN_TTL[kind],
    )
    return token


async def peek_token(conn, token: str, kind: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        "select t.account_id, t.email, a.email as account_email from web.auth_tokens t"
        " join web.accounts a on a.id = t.account_id"
        " where t.token_hash = $1 and t.kind = $2 and t.used_at is null and t.expires_at > now()",
        hash_token(token),
        kind,
    )
    if row is None or row["email"] != row["account_email"]:
        raise ApiError(400, "invalid_token")
    return row


async def consume_token(conn, token: str, kind: str) -> asyncpg.Record:
    """Marks the token used; atomic, so a token works exactly once."""
    row = await peek_token(conn, token, kind)
    done = await conn.fetchval(
        "update web.auth_tokens set used_at = now()"
        " where token_hash = $1 and used_at is null returning 1",
        hash_token(token),
    )
    if not done:
        raise ApiError(400, "invalid_token")
    return row
