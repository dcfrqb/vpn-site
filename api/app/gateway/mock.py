import hashlib
import random
from datetime import UTC, datetime, timedelta, timezone

from app.gateway.base import (
    BotCabinet,
    CabinetDevice,
    CabinetNode,
    CabinetPayment,
    CabinetStats,
    CabinetSubscription,
    CabinetUser,
    NetworkStatus,
    Node,
    NodeTraffic,
    Plan,
    SubTraffic,
    TrafficDay,
    TrafficMonth,
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

# Nodes a cabinet shows. Placeholder names, not real node ids.
_CAB_NODES = [
    ("nl-1", "nl"),
    ("nl-2", "nl"),
    ("fr-1", "fr"),
    ("fr-2", "fr"),
    ("us-3", "us"),
    ("es-1", "es"),
    ("ru-1", "ru"),
]
_DEVICES = [
    ("iOS", "19.0", "iPhone16,2", "Happ/3.1"),
    ("iOS", "18.6", "iPhone14,5", "Karing/1.2"),
    ("Android", "15", "Pixel 8", "Happ/2.9"),
    ("Android", "14", "SM-S918B", "Clash Mi/1.0"),
    ("macOS", "26.0", "MacBookAir10,1", "Happ/3.1"),
    ("Windows", "11", "Desktop", "Karing/1.2"),
    ("iPadOS", "19.0", "iPad13,18", "Happ/3.1"),
]
_MSK = timezone(timedelta(hours=3))
_GB = 1024**3
_OBHOD_LIMIT = 100 * _GB

# Owner preview (GET /api/cabinet?demo=...): fixed states of a paid subscription.
SCENARIOS = ("active", "expiring", "expired", "none")


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

    async def delete_device(self, telegram_id: int, hwid: str) -> bool:
        # Demo data is regenerated on every call, so a delete cannot stick; answer as the bot
        # would for an own device and let the page update optimistically.
        cab = await self.cabinet(telegram_id)
        return any(d.hwid == hwid for d in cab.devices)

    async def cabinet(self, telegram_id: int, scenario: str | None = None) -> BotCabinet:
        # Demo data seeded by the telegram id: stable for one user, different between users.
        # `scenario` (one of SCENARIOS) pins the subscription state for the owner preview.
        rng = random.Random(telegram_id)  # noqa: S311 - not security related
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        today = now.astimezone(_MSK).date()
        plan = _PLANS[1] if rng.random() < 0.7 else _PLANS[0]  # standard, sometimes lite
        has_obhod = rng.random() < 0.5
        days_left = rng.randint(3, 120)
        status = "active"
        if scenario is not None:
            plan = _PLANS[1]
            has_obhod = scenario in ("active", "expiring")
            days_left = {"active": 35, "expiring": 3}.get(scenario, 0)
            status = "expired" if scenario in ("expired", "none") else "active"
        valid_until = (now + timedelta(days=days_left)).replace(hour=0)
        if status == "expired":
            valid_until = (now - timedelta(days=12)).replace(hour=0)
        token = hashlib.sha256(f"demo:{telegram_id}".encode()).hexdigest()

        # 30 days of traffic, oldest first; obhod days are small and bursty.
        daily = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            weekend = day.weekday() >= 5
            main = int(rng.uniform(0.2, 4.5 if weekend else 3.0) * _GB)
            if rng.random() < 0.1:
                main = 0
            obhod = int(rng.uniform(0.3, 5.0) * _GB) if has_obhod and rng.random() < 0.7 else 0
            daily.append(TrafficDay(date=day, main_bytes=main, obhod_bytes=obhod))
        month = [d for d in daily if d.date.month == today.month]
        main_month = sum(d.main_bytes for d in month)
        obhod_month = sum(d.obhod_bytes for d in month)
        if has_obhod and rng.random() < 0.4:
            obhod_month = int(rng.uniform(0.82, 0.97) * _OBHOD_LIMIT)  # near the cap

        subs = [
            CabinetSubscription(
                kind="main",
                plan_code=plan.code,
                plan_title=plan.title.capitalize(),
                status=status,
                valid_until=valid_until,
                days_left=days_left,
                device_limit=plan.device_limit,
                sub_url=f"https://sub.example.com/demo-{token[:16]}",
                traffic=SubTraffic(
                    used_bytes=main_month + int(rng.uniform(40, 400) * _GB),
                    limit_bytes=None,
                    reset="none",
                    month_used_bytes=main_month,
                    lifetime_used_bytes=main_month + int(rng.uniform(300, 1500) * _GB),
                ),
                online_at=now - timedelta(minutes=rng.randint(1, 90)),
                last_node=rng.choice(["nl-1", "nl-2", "fr-1"]),
            )
        ]
        if has_obhod:
            subs.append(
                CabinetSubscription(
                    kind="obhod",
                    plan_code="pro",
                    plan_title="RU-вход",
                    status="active",
                    valid_until=valid_until,
                    days_left=days_left,
                    device_limit=10,
                    sub_url=f"https://sub.example.com/demo-{token[16:32]}",
                    traffic=SubTraffic(
                        used_bytes=obhod_month,
                        limit_bytes=_OBHOD_LIMIT,
                        reset="month",
                        month_used_bytes=obhod_month,
                        lifetime_used_bytes=obhod_month + int(rng.uniform(50, 300) * _GB),
                    ),
                    package=None,
                    online_at=None,
                    last_node=None,
                )
            )

        devices = []
        for n, (platform, os_version, model, app) in enumerate(
            rng.sample(_DEVICES, rng.randint(2, 4))
        ):
            first = now - timedelta(days=rng.randint(20, 200))
            devices.append(
                CabinetDevice(
                    subscription="obhod" if has_obhod and n == 1 else "main",
                    hwid=hashlib.sha256(f"{token}:{n}".encode()).hexdigest()[:24],
                    platform=platform,
                    os_version=os_version,
                    model=model,
                    app=app,
                    first_seen_at=first,
                    last_seen_at=now - timedelta(minutes=rng.randint(1, 60 * 24 * 9)),
                )
            )

        # Monthly bars since the first paid month: the current month from the daily data.
        history = rng.randint(6, 16)
        traffic_monthly = []
        for back in range(history - 1, -1, -1):
            idx = today.year * 12 + today.month - 1 - back
            key = f"{idx // 12:04d}-{idx % 12 + 1:02d}"
            if back == 0:
                traffic_monthly.append(
                    TrafficMonth(month=key, main_bytes=main_month, obhod_bytes=obhod_month)
                )
                continue
            main_m = int(rng.uniform(15, 90) * _GB)
            obhod_m = int(rng.uniform(5, 80) * _GB) if has_obhod and back < history // 2 else 0
            traffic_monthly.append(TrafficMonth(month=key, main_bytes=main_m, obhod_bytes=obhod_m))

        by_node: dict[str, int] = {}
        for name, _ in _CAB_NODES[:-1]:
            by_node[name] = int(sum(d.main_bytes for d in daily) * rng.uniform(0, 1))
        total_main = sum(d.main_bytes for d in daily)
        weight = sum(by_node.values()) or 1
        traffic_by_node = [
            NodeTraffic(node=name, country=c, bytes_30d=by_node[name] * total_main // weight)
            for name, c in _CAB_NODES[:-1]
            if by_node[name] > 0
        ]
        if has_obhod:
            traffic_by_node.append(
                NodeTraffic(node="ru-1", country="ru", bytes_30d=sum(d.obhod_bytes for d in daily))
            )
        traffic_by_node.sort(key=lambda t: t.bytes_30d, reverse=True)

        payments = []
        paid_at = now - timedelta(days=rng.randint(3, 25), hours=rng.randint(0, 12))
        count = rng.randint(3, 6)
        for n in range(count):
            months = rng.choice([1, 1, 1, 3, 6])
            status = "succeeded"
            if n == 0 and rng.random() < 0.25:
                status = "pending"
            elif n > 0 and rng.random() < 0.15:
                status = "canceled"
            payments.append(
                CabinetPayment(
                    id=1000 + telegram_id % 900 * 7 + count - n,
                    created_at=paid_at,
                    paid_at=paid_at + timedelta(minutes=1) if status == "succeeded" else None,
                    provider="yookassa",
                    status=status,
                    amount_rub=float(plan.prices[months]),
                    plan_code=plan.code,
                    period_months=months,
                    kind="subscription",
                    description=f"{plan.title.capitalize()}, {months} мес",
                )
            )
            paid_at -= timedelta(days=30 * months, hours=rng.randint(0, 20))
        ok = [p for p in payments if p.status == "succeeded" and p.kind != "promo"]
        stats = CabinetStats(
            payments_count=len(ok),
            paid_total_rub=sum(p.amount_rub for p in ok),
            first_payment_at=min((p.paid_at for p in ok if p.paid_at), default=None),
            last_payment_at=max((p.paid_at for p in ok if p.paid_at), default=None),
        )

        if scenario == "none":
            subs, devices, traffic_by_node, traffic_monthly, payments = [], [], [], [], []
            stats = CabinetStats()
            daily = [TrafficDay(date=d.date) for d in daily]
        elif scenario == "expired":
            # no traffic since it ran out
            cutoff = today - timedelta(days=11)
            daily = [d if d.date < cutoff else TrafficDay(date=d.date) for d in daily]

        return BotCabinet(
            generated_at=now,
            partial=False,
            errors=[],
            user=CabinetUser(
                telegram_id=telegram_id,
                username=None,
                first_name=None,
                customer_since=payments[-1].created_at if payments else None,
            ),
            subscriptions=subs,
            devices=devices,
            traffic_daily=daily,
            traffic_by_node=traffic_by_node,
            traffic_monthly=traffic_monthly,
            payments=payments,
            stats=stats,
            nodes=[
                CabinetNode(name=name, country=c, online=rng.random() > 0.08)
                for name, c in _CAB_NODES
            ],
        )
