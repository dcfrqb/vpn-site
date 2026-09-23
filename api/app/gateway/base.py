import datetime as dt
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict


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


class _Tolerant(BaseModel):
    """Bot JSON: unknown fields are ignored so a newer bot does not break the site."""

    model_config = ConfigDict(extra="ignore")


class CabinetUser(_Tolerant):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    customer_since: datetime | None = None


class SubTraffic(_Tolerant):
    used_bytes: int | None = None
    limit_bytes: int | None = None
    reset: str = "none"
    month_used_bytes: int | None = None


class ObhodPackage(_Tolerant):
    code: str
    until: datetime | None = None
    limit_bytes: int | None = None


class CabinetSubscription(_Tolerant):
    kind: str  # main | obhod
    plan_code: str | None = None
    plan_title: str | None = None
    legacy: bool = False
    status: str  # active | expired | disabled | limited | unknown (panel down)
    valid_until: datetime | None = None
    is_lifetime: bool = False
    days_left: int | None = None
    device_limit: int | None = None
    sub_url: str | None = None
    traffic: SubTraffic | None = None
    package: ObhodPackage | None = None
    online_at: datetime | None = None
    last_node: str | None = None


class CabinetDevice(_Tolerant):
    subscription: str
    hwid: str
    platform: str | None = None
    os_version: str | None = None
    model: str | None = None
    app: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class TrafficDay(_Tolerant):
    date: dt.date
    main_bytes: int = 0
    obhod_bytes: int = 0


class NodeTraffic(_Tolerant):
    node: str
    country: str | None = None
    bytes_30d: int = 0


class CabinetPayment(_Tolerant):
    id: int
    created_at: datetime
    paid_at: datetime | None = None
    provider: str | None = None
    status: str
    amount_rub: float
    plan_code: str | None = None
    period_months: int | None = None
    kind: str = "subscription"  # subscription | obhod_package | promo
    description: str | None = None


class CabinetStats(_Tolerant):
    payments_count: int = 0
    paid_total_rub: float = 0
    first_payment_at: datetime | None = None
    last_payment_at: datetime | None = None


class CabinetNode(_Tolerant):
    name: str
    country: str | None = None
    online: bool = False


class BotAccount(_Tolerant):
    kind: str  # main | obhod
    # Remnawave 3.x addresses users by numeric id; remna_uuid is accepted when it holds that id.
    remna_id: int | None = None
    remna_uuid: str | None = None
    plan_code: str | None = None
    plan_title: str | None = None
    legacy: bool = False
    device_limit: int | None = None
    package: ObhodPackage | None = None

    @property
    def panel_id(self) -> int | None:
        if self.remna_id is not None:
            return self.remna_id
        if self.remna_uuid and self.remna_uuid.isdigit():
            return int(self.remna_uuid)
        return None


class BotProfile(_Tolerant):
    """GET {BOT_API_URL}/internal/site/users/{telegram_id}/profile: ownership, plans, payments."""

    user: CabinetUser
    accounts: list[BotAccount] = []
    payments: list[CabinetPayment] = []
    stats: CabinetStats = CabinetStats()


class BotCabinet(_Tolerant):
    """What the site shows (shape of bot-site-cabinet-api-spec.md), composed from bot + panel."""

    generated_at: datetime
    partial: bool = False
    errors: list[str] = []
    user: CabinetUser
    subscriptions: list[CabinetSubscription] = []
    devices: list[CabinetDevice] = []
    traffic_daily: list[TrafficDay] = []
    traffic_by_node: list[NodeTraffic] = []
    payments: list[CabinetPayment] = []
    stats: CabinetStats = CabinetStats()
    nodes: list[CabinetNode] = []


class CabinetResponse(BaseModel):
    """What the site returns on GET /api/cabinet."""

    linked: bool
    demo: bool
    data: BotCabinet | None = None


class GatewayUnavailable(Exception):  # noqa: N818 - reads better at the call site
    """The bot did not answer, answered 5xx or with something we cannot parse."""


class BotGateway(Protocol):
    async def list_plans(self) -> list[Plan]: ...

    async def network_status(self) -> NetworkStatus: ...

    async def cabinet(self, telegram_id: int) -> BotCabinet | None:
        """None when the bot does not know this telegram id. Raises GatewayUnavailable."""
        ...

    async def delete_device(self, telegram_id: int, hwid: str) -> bool:
        """False when the hwid does not belong to this telegram id. Raises GatewayUnavailable."""
        ...
