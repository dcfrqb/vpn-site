from typing import Protocol

from pydantic import BaseModel


class Plan(BaseModel):
    code: str
    title: str
    device_limit: int
    countries: list[str]
    prices: dict[int, int]  # months -> RUB
    ru_entry_gb: int | None = None
    highlighted: bool = False


class Node(BaseModel):
    name: str
    country: str
    online: bool


class NetworkStatus(BaseModel):
    nodes_total: int
    nodes_online: int
    exit_countries: list[str]
    nodes: list[Node]


class BotGateway(Protocol):
    async def list_plans(self) -> list[Plan]: ...

    async def network_status(self) -> NetworkStatus: ...
