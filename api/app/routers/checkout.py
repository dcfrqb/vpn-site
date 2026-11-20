from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.accounts import CurrentAuth
from app.checkout_bridge import bridge
from app.config import get_settings
from app.errors import ApiError
from app.security import client_host, limiter

router = APIRouter(prefix="/checkout")


class QuoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_code: str = Field(min_length=1, max_length=32)
    months: int = Field(ge=1, le=12)


class OrderIn(QuoteIn):
    order_id: UUID
    expected_amount_rub: int = Field(gt=0)


def enabled():
    if not get_settings().site_checkout_enabled:
        raise ApiError(503, "checkout_unavailable")


def identity(auth):
    return {"account_id": str(auth.account_id), "telegram_id": auth.account["telegram_id"]}


@router.get("/config")
async def config():
    return {"enabled": get_settings().site_checkout_enabled}


@router.post("/quote")
async def quote(body: QuoteIn, auth: CurrentAuth, request: Request):
    enabled()
    limiter.hit("checkout_quote", client_host(request), str(auth.account_id))
    return await bridge.request(
        "POST", "/internal/site/checkout/quote", {**body.model_dump(), **identity(auth)}
    )


@router.post("/orders")
async def create_order(body: OrderIn, auth: CurrentAuth, request: Request):
    enabled()
    limiter.hit("checkout_start", client_host(request), str(auth.account_id))
    return await bridge.request(
        "POST", "/internal/site/checkout/orders", {**body.model_dump(mode="json"), **identity(auth)}
    )


@router.get("/orders/{order_id}")
async def order(order_id: UUID, auth: CurrentAuth, request: Request):
    enabled()
    limiter.hit("checkout_status", client_host(request), str(auth.account_id))
    return await bridge.request(
        "GET", f"/internal/site/checkout/accounts/{auth.account_id}/orders/{order_id}"
    )
