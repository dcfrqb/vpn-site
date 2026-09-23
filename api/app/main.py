from fastapi import FastAPI

from app.routers import health, public

app = FastAPI(title="vpn-site api", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(health.router, prefix="/api")
app.include_router(public.router, prefix="/api")
