from typing import Annotated

from fastapi import APIRouter, Depends

from app.accounts import CurrentAuth
from app.gateway import get_gateway
from app.gateway.base import BotGateway, Cabinet

router = APIRouter()


@router.get("/cabinet")
async def cabinet(auth: CurrentAuth, gw: Annotated[BotGateway, Depends(get_gateway)]) -> Cabinet:
    telegram_id = auth.account["telegram_id"]
    if telegram_id is None:
        return Cabinet(linked=False)
    return await gw.cabinet(telegram_id)
