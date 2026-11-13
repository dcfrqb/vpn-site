import asyncpg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from app import google_identity
from app.accounts import (
    CurrentAuth,
    MaybeAuth,
    account_json,
    audit,
    ensure_other_login_method,
    get_account,
    start_session,
)
from app.config import get_settings
from app.db import Conn
from app.errors import ApiError
from app.security import client_host, hash_token, limiter, new_token

router = APIRouter()
TTL = 600


def cookie_name() -> str:
    return "__Host-google-nonce" if get_settings().cookie_secure else "google-nonce"


class GoogleIn(BaseModel):
    credential: str = Field(min_length=1, max_length=16384)


@router.get("/auth/google/config")
async def config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": bool(get_settings().google_client_id)}


@router.post("/auth/google/options")
async def options(request: Request, response: Response, conn: Conn, auth: MaybeAuth):
    client_id = get_settings().google_client_id
    if not client_id:
        raise ApiError(503, "google_unavailable")
    limiter.hit("login", "google-options:" + client_host(request))
    nonce, nonce_hash = new_token()
    async with conn.transaction():
        await conn.execute("delete from web.google_challenges where expires_at < now()")
        await conn.execute(
            "insert into web.google_challenges values ($1, $2, now() + interval '10 minutes')",
            nonce_hash,
            auth.account_id if auth else None,
        )
    response.set_cookie(
        cookie_name(),
        nonce,
        max_age=TTL,
        secure=get_settings().cookie_secure,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"client_id": client_id, "nonce": nonce}


@router.post("/auth/google")
async def login(body: GoogleIn, request: Request, response: Response, conn: Conn, auth: MaybeAuth):
    client_id = get_settings().google_client_id
    if not client_id:
        raise ApiError(503, "google_unavailable")
    limiter.hit("login", "google:" + client_host(request))
    nonce = request.cookies.get(cookie_name(), "")
    if not nonce or len(nonce) > 128:
        raise ApiError(401, "google_invalid")
    account_id = auth.account_id if auth else None
    valid = await conn.fetchval(
        "select exists(select 1 from web.google_challenges where nonce_hash = $1"
        " and expires_at > now() and account_id is not distinct from $2::uuid)",
        hash_token(nonce),
        account_id,
    )
    if not valid:
        raise ApiError(401, "google_invalid")
    identity = await google_identity.verify(body.credential, client_id, nonce)
    try:
        async with conn.transaction():
            # Serialize first-time linking for the same Google identity across browsers.
            await conn.execute(
                "select pg_advisory_xact_lock(hashtextextended($1, 0))",
                "google:" + identity["sub"],
            )
            consumed = await conn.fetchval(
                "delete from web.google_challenges where nonce_hash = $1 and expires_at > now()"
                " and account_id is not distinct from $2::uuid returning nonce_hash",
                hash_token(nonce),
                account_id,
            )
            if consumed is None:
                raise ApiError(401, "google_invalid")
            owner = await conn.fetchval(
                "select account_id from web.google_identities where subject = $1", identity["sub"]
            )
            if auth:
                if owner is not None and owner != account_id:
                    raise ApiError(409, "google_taken")
                other = await conn.fetchval(
                    "select subject from web.google_identities where account_id = $1", account_id
                )
                if other is not None and other != identity["sub"]:
                    raise ApiError(409, "google_taken")
            elif owner is not None:
                account_id = owner
            else:
                existing = await conn.fetchrow(
                    "select id from web.accounts where email = $1 for update", identity["email"]
                )
                if existing:
                    if not identity["authoritative"]:
                        raise ApiError(409, "google_link_required")
                    account_id = existing["id"]
                    if await conn.fetchval(
                        "select subject from web.google_identities where account_id = $1",
                        account_id,
                    ):
                        raise ApiError(409, "google_taken")
                    await conn.execute(
                        "update web.accounts set email_verified_at ="
                        " coalesce(email_verified_at, now())"
                        " where id = $1",
                        account_id,
                    )
                    await audit(conn, request, "google_link", account_id, method="verified_email")
                else:
                    account_id = await conn.fetchval(
                        "insert into web.accounts (email, email_verified_at)"
                        " values ($1, case when $2 then now() end) returning id",
                        identity["email"],
                        identity["authoritative"],
                    )
                    await audit(conn, request, "register", account_id, method="google")
            await conn.execute(
                "insert into web.google_identities (subject, account_id, email) values ($1,$2,$3)"
                " on conflict (subject) do update set email = excluded.email",
                identity["sub"],
                account_id,
                identity["email"],
            )
            if auth:
                await audit(conn, request, "google_link", account_id)
            else:
                await start_session(conn, request, response, account_id, "google")
    except asyncpg.UniqueViolationError:
        raise ApiError(409, "google_link_required") from None
    response.delete_cookie(cookie_name(), path="/", secure=get_settings().cookie_secure)
    return {"account": await account_json(conn, await get_account(conn, account_id))}


@router.delete("/me/google", status_code=204)
async def unlink(auth: CurrentAuth, request: Request, conn: Conn):
    await ensure_other_login_method(conn, auth.account, "google")
    await conn.execute("delete from web.google_identities where account_id = $1", auth.account_id)
    await audit(conn, request, "google_unlink", auth.account_id)
