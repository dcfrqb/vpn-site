"""Website session -> internal billing API. No merchant keys or prices from browsers."""

from uuid import UUID

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.errors import ApiError
from app.gateway.base import BotProfile, Plan

ALLOWED_ERRORS = {
    "checkout_unavailable",
    "checkout_busy",
    "plan_unavailable",
    "account_conflict",
    "price_changed",
    "order_not_found",
    "order_conflict",
    "order_in_progress",
    "payment_unavailable",
    "payment_mismatch",
    "subscription_needs_review",
    "provisioning_pending",
}


class CheckoutBridge:
    async def request(self, method, path, body=None):
        s = get_settings()
        if not s.bot_api_url or not s.bot_api_token:
            raise ApiError(503, "checkout_unavailable")
        try:
            async with httpx.AsyncClient(
                base_url=s.bot_api_url.rstrip("/"),
                timeout=60,
                headers={"X-Internal-Token": s.bot_api_token, "Accept": "application/json"},
            ) as client:
                response = await client.request(method, path, json=body)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise ApiError(503, "checkout_unavailable") from None
        if response.status_code >= 400:
            code = data.get("error") if isinstance(data, dict) else None
            extra = {}
            if code == "order_in_progress":
                try:
                    extra["order_id"] = str(UUID(data.get("order_id", "")))
                except (ValueError, TypeError):
                    pass
            if code in ALLOWED_ERRORS and response.status_code in {400, 404, 409}:
                raise ApiError(response.status_code, code, **extra)
            raise ApiError(503, "checkout_unavailable")
        return data

    async def catalog(self):
        data = await self.request("GET", "/internal/site/catalog")
        try:
            return [Plan.model_validate(plan) for plan in data["plans"]]
        except (KeyError, TypeError, ValidationError):
            raise ApiError(503, "checkout_unavailable") from None

    async def profile(self, account):
        query = f"?telegram_id={account['telegram_id']}" if account["telegram_id"] else ""
        data = await self.request("GET", f"/internal/site/accounts/{account['id']}/profile{query}")
        if data is None:
            return None
        try:
            return BotProfile.model_validate(data)
        except ValidationError:
            raise ApiError(503, "checkout_unavailable") from None


bridge = CheckoutBridge()
