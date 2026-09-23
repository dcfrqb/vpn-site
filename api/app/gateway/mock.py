import hashlib
import random
from datetime import UTC, datetime, timedelta

from app.gateway.base import (
    Cabinet,
    CabinetNode,
    Device,
    NetworkStatus,
    Node,
    Payment,
    Plan,
    Subscription,
)

# Prices mirror the bot catalog (src/app/core/plans.py, release 3.0, 23.09.2026).
_PLANS = [
    Plan(
        code="lite",
        title="lite",
        device_limit=2,
        countries=["nl"],
        prices={1: 129, 3: 329, 6: 599, 12: 1099},
    ),
    Plan(
        code="standard",
        title="standard",
        device_limit=5,
        countries=["nl", "fr"],
        prices={1: 249, 3: 649, 6: 1199, 12: 2199},
        highlighted=True,
    ),
    Plan(
        code="pro",
        title="pro",
        device_limit=10,
        countries=["nl", "fr", "us", "es"],
        prices={1: 449, 3: 1199, 6: 2199, 12: 3999},
        ru_entry_gb=100,
    ),
]

# Placeholder names, not real node ids.
_NODES = [
    Node(name="nl-1", country="nl", online=True),
    Node(name="nl-2", country="nl", online=True),
    Node(name="nl-3", country="nl", online=True),
    Node(name="fr-1", country="fr", online=True),
    Node(name="fr-2", country="fr", online=True),
    Node(name="us-1", country="us", online=True),
    Node(name="us-2", country="us", online=True),
    Node(name="es-1", country="es", online=True),
    Node(name="ru-1", country="ru", online=True),
]

_DEVICES = ["iPhone", "MacBook", "Android", "Windows PC", "iPad", "Android TV"]
_PING = {"nl": (38, 60), "fr": (45, 70), "us": (120, 160), "es": (60, 85), "ru": (8, 20)}


class MockGateway:
    async def list_plans(self) -> list[Plan]:
        return [p.model_copy(deep=True) for p in _PLANS]

    async def network_status(self) -> NetworkStatus:
        nodes = [n.model_copy() for n in _NODES]
        return NetworkStatus(
            nodes_total=len(nodes),
            nodes_online=sum(n.online for n in nodes),
            exit_countries=["nl", "fr", "us", "es"],
            nodes=nodes,
        )

    async def cabinet(self, telegram_id: int) -> Cabinet:
        # Demo data seeded by the telegram id: stable for one user, different between users.
        rng = random.Random(telegram_id)  # noqa: S311 - not security related
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        plan = rng.choice(_PLANS)
        days_left = rng.randint(3, 180)
        payments = []
        paid_at = now - timedelta(days=rng.randint(5, 25))
        for _ in range(rng.randint(1, 4)):
            months = rng.choice(list(plan.prices))
            payments.append(
                Payment(
                    date=paid_at.date(),
                    plan=plan.code,
                    months=months,
                    amount_rub=plan.prices[months],
                    status="succeeded",
                )
            )
            paid_at -= timedelta(days=30 * months)
        countries = set(plan.countries) | ({"ru"} if plan.ru_entry_gb else set())
        token = hashlib.sha256(f"demo:{telegram_id}".encode()).hexdigest()[:16]
        return Cabinet(
            linked=True,
            subscription=Subscription(
                plan=plan.code,
                status="active",
                valid_until=now + timedelta(days=days_left),
                days_left=days_left,
                device_limit=plan.device_limit,
                sub_url=f"https://sub.example.com/demo-{token}",
                traffic_month_gb=round(rng.uniform(3, 120), 1),
            ),
            devices=[
                Device(name=name, last_seen_at=now - timedelta(minutes=rng.randint(1, 60 * 72)))
                for name in rng.sample(_DEVICES, rng.randint(2, min(4, plan.device_limit)))
            ],
            payments=payments,
            nodes=[
                CabinetNode(
                    name=n.name,
                    country=n.country,
                    online=n.online,
                    ping_ms=rng.randint(*_PING[n.country]),
                )
                for n in _NODES
                if n.country in countries
            ],
            demo=True,
        )
