from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.accounts import CurrentAuth, audit
from app.db import Conn
from app.errors import ApiError
from app.gateway import get_gateway, is_demo
from app.gateway.base import BotGateway, CabinetResponse, GatewayUnavailable
from app.gateway.mock import SCENARIOS, MockGateway

router = APIRouter()
Gateway = Annotated[BotGateway, Depends(get_gateway)]


@router.get("/cabinet")
async def cabinet(
    auth: CurrentAuth, gw: Gateway, demo_scenario: Annotated[str | None, Query(alias="demo")] = None
) -> CabinetResponse:
    telegram_id = auth.account["telegram_id"]
    if demo_scenario is not None:
        # Owner preview of states his own account is not in: always mock data, marked demo.
        if demo_scenario not in SCENARIOS:
            raise ApiError(400, "invalid_request")
        data = await MockGateway().cabinet(telegram_id or 0, scenario=demo_scenario)
        return CabinetResponse(linked=True, demo=True, data=data)
    demo = is_demo(gw)
    if telegram_id is None:
        return CabinetResponse(linked=False, demo=demo)
    try:
        data = await gw.cabinet(telegram_id)
    except GatewayUnavailable:
        raise ApiError(503, "bot_unavailable") from None
    return CabinetResponse(linked=True, demo=demo, data=data)


@router.delete("/cabinet/devices/{hwid:path}", status_code=204)
async def delete_device(
    hwid: str, request: Request, auth: CurrentAuth, gw: Gateway, conn: Conn
) -> Response:
    telegram_id = auth.account["telegram_id"]
    if telegram_id is None or not hwid or len(hwid) > 256:
        raise ApiError(404, "device_not_found")
    try:
        ok = await gw.delete_device(telegram_id, hwid)
    except GatewayUnavailable:
        raise ApiError(503, "bot_unavailable") from None
    await audit(conn, request, "device_delete", auth.account_id, hwid=hwid[:6], ok=ok)
    if not ok:
        raise ApiError(404, "device_not_found")
    return Response(status_code=204)
