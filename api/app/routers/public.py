from typing import Annotated

from fastapi import APIRouter, Depends

from app.gateway import get_gateway
from app.gateway.base import BotGateway, NetworkStatus, Plan

router = APIRouter()
Gateway = Annotated[BotGateway, Depends(get_gateway)]


@router.get("/plans")
async def plans(gw: Gateway) -> list[Plan]:
    return await gw.list_plans()


@router.get("/network")
async def network(gw: Gateway) -> NetworkStatus:
    return await gw.network_status()
