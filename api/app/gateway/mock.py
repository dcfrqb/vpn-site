from app.gateway.base import NetworkStatus, Node, Plan

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
