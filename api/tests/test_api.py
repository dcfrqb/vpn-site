from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_without_db():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["db"] is None


def test_plans_match_bot_catalog():
    plans = {p["code"]: p for p in client.get("/api/plans").json()}
    assert set(plans) == {"lite", "standard", "pro"}
    assert plans["lite"]["prices"]["1"] == 129
    assert plans["standard"]["prices"]["12"] == 2199
    assert plans["pro"]["prices"]["1"] == 449
    assert plans["pro"]["ru_entry_gb"] == 100


def test_network_counts():
    net = client.get("/api/network").json()
    assert net["nodes_total"] == len(net["nodes"])
    assert net["exit_countries"] == ["nl", "fr", "us", "es"]


def test_docs_are_closed():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
