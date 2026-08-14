import importlib
from unittest.mock import MagicMock

import psycopg
import pytest


@pytest.fixture()
def app_module(monkeypatch):
    monkeypatch.setenv("FEATURE_STATS", "false")
    return importlib.import_module("app.app")


@pytest.fixture()
def client(app_module):
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


def fake_connection(*, result=(1,)):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = result
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = result
    connection.cursor.return_value = cursor
    return connection


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def test_request_id_is_propagated(client):
    response = client.get("/health", headers={"X-Request-ID": "course-request-42"})
    assert response.headers["X-Request-ID"] == "course-request-42"


def test_index_exposes_version(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "test-sha")
    response = client.get("/")
    assert response.status_code == 200
    assert response.get_json()["version"] == "test-sha"


def test_stats_is_disabled_by_default(client):
    response = client.get("/stats")
    assert response.status_code == 404
    assert response.get_json() == {"error": "feature-disabled"}


def test_stats_returns_database_count(client, app_module, monkeypatch):
    monkeypatch.setenv("FEATURE_STATS", "true")
    connection = fake_connection(result=(7,))
    monkeypatch.setattr(app_module.psycopg, "connect", lambda *args, **kwargs: connection)

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.get_json() == {"total_visits": 7}


def test_visits_increments_and_returns_count(client, app_module, monkeypatch):
    connection = fake_connection(result=(3,))
    monkeypatch.setattr(app_module.psycopg, "connect", lambda *args, **kwargs: connection)

    response = client.get("/visits")

    assert response.status_code == 200
    assert response.get_json() == {"visits": 3}
    executed_queries = [call.args[0] for call in connection.cursor.return_value.execute.call_args_list]
    assert "INSERT INTO visits DEFAULT VALUES" in executed_queries


def test_ready_when_database_is_available(client, app_module, monkeypatch):
    connection = fake_connection()
    monkeypatch.setattr(app_module.psycopg, "connect", lambda *args, **kwargs: connection)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}


def test_not_ready_when_database_is_unavailable(client, app_module, monkeypatch):
    def unavailable(*args, **kwargs):
        raise psycopg.OperationalError("database unavailable")

    monkeypatch.setattr(app_module.psycopg, "connect", unavailable)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {"status": "not-ready"}


def test_metrics(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"app_requests_total" in response.data
