import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db, errors
from app.gateway import close_gateway
from app.routers import auth, cabinet, health, me, public, tg_app, tg_bot_bridge
from app.security import OriginCheckMiddleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await db.open_pool()
    try:
        yield
    finally:
        await close_gateway()
        await db.close_pool()


app = FastAPI(
    title="vpn-site api", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
)
app.add_middleware(OriginCheckMiddleware)
errors.install(app)
for r in (health, public, auth, tg_app, tg_bot_bridge, me, cabinet):
    app.include_router(r.router, prefix="/api")
