from datetime import date, datetime
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


class Subscription(BaseModel):
    plan: str
    status: str
    valid_until: datetime
    days_left: int
    device_limit: int
    sub_url: str
    traffic_month_gb: float


class Device(BaseModel):
    name: str
    last_seen_at: datetime


class Payment(BaseModel):
    date: date
    plan: str
    months: int
    amount_rub: int
    status: str


class CabinetNode(BaseModel):
    name: str
    country: str
    online: bool
    ping_ms: int | None


class Cabinet(BaseModel):
    linked: bool
    subscription: Subscription | None = None
    devices: list[Device] = []
    payments: list[Payment] = []
    nodes: list[CabinetNode] = []
    demo: bool = True


class BotGateway(Protocol):
    async def list_plans(self) -> list[Plan]: ...

    async def network_status(self) -> NetworkStatus: ...

    async def cabinet(self, telegram_id: int) -> Cabinet: ...
