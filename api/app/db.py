import asyncpg

from app.config import get_settings


async def ping() -> bool | None:
    """True/False if the database answers, None if it is not configured."""
    url = get_settings().database_url
    if not url:
        return None
    try:
        conn = await asyncpg.connect(url, timeout=3)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        return False
    try:
        return await conn.fetchval("select 1") == 1
    finally:
        await conn.close()
