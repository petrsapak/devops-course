import importlib

import pytest


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("FEATURE_STATS", "false")
    module = importlib.import_module("app.app")
    module.app.config.update(TESTING=True)
    return module.app.test_client()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_index_exposes_version(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-sha")
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json()["version"] == "test-sha"


def test_stats_is_disabled_by_default(client):
    response = client.get("/stats")
    assert response.status_code == 404
    assert response.get_json() == {"error": "feature-disabled"}


def test_metrics(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"app_requests_total" in response.data
