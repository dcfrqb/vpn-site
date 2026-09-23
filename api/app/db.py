import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

import asyncpg
from fastapi import Depends

from app.config import get_settings
from app.errors import ApiError

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_LOCK_ID = 0x7670_6E73_6974_65  # "vpnsite", any constant shared by all api replicas

pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def migrate(conn: asyncpg.Connection) -> list[str]:
    """Apply pending migrations/NNNN_*.sql in one transaction under an advisory lock."""
    applied_now = []
    async with conn.transaction():
        await conn.execute("select pg_advisory_xact_lock($1)", _LOCK_ID)
        await conn.execute(
            # Checked by hand: IF NOT EXISTS still needs CREATE on the database.
            "do $$ begin if not exists (select from pg_namespace where nspname = 'web')"
            " then create schema web; end if; end $$;"
            "create table if not exists web.schema_migrations"
            " (version text primary key, applied_at timestamptz not null default now())"
        )
        done = {r["version"] for r in await conn.fetch("select version from web.schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in done:
                continue
            await conn.execute(path.read_text())
            await conn.execute("insert into web.schema_migrations (version) values ($1)", path.stem)
            applied_now.append(path.stem)
    if applied_now:
        log.info("applied migrations: %s", ", ".join(applied_now))
    return applied_now


async def open_pool() -> None:
    global pool
    url = get_settings().database_url
    if not url or pool is not None:
        return
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5, init=_init_conn)
    async with pool.acquire() as conn:
        await migrate(conn)


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def get_conn() -> AsyncIterator[asyncpg.Connection]:
    if pool is None:
        raise ApiError(503, "unavailable")
    async with pool.acquire() as conn:
        yield conn


Conn = Annotated[asyncpg.Connection, Depends(get_conn)]


async def ping() -> bool | None:
    """True/False if the database answers, None if it is not configured."""
    if not get_settings().database_url:
        return None
    try:
        if pool is not None:
            return await pool.fetchval("select 1", timeout=3) == 1
        conn = await asyncpg.connect(get_settings().database_url, timeout=3)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        return False
    try:
        return await conn.fetchval("select 1") == 1
    finally:
        await conn.close()
