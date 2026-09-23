from fastapi import APIRouter, Response

from app import db
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    db_ok = await db.ping()
    ok = db_ok is not False
    if not ok:
        response.status_code = 503
    return {"ok": ok, "version": get_settings().git_sha, "db": db_ok}
