import importlib
import os
import time

import psycopg
import pytest

from app import worker


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration tests",
)


@pytest.fixture()
def clean_database():
    deadline = time.monotonic() + 30
    while True:
        try:
            with psycopg.connect(DATABASE_URL) as connection:
                connection.execute("SELECT 1")
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                pytest.fail("PostgreSQL did not become ready within 30 seconds")
            time.sleep(1)

    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute("DROP TABLE IF EXISTS visits")
        connection.execute("DROP TABLE IF EXISTS reports")
    yield
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute("DROP TABLE IF EXISTS visits")
        connection.execute("DROP TABLE IF EXISTS reports")


def test_api_and_worker_database_flow(monkeypatch, clean_database):
    monkeypatch.setenv("DATABASE_URL", DATABASE_URL)
    monkeypatch.setenv("FEATURE_STATS", "true")
    app_module = importlib.import_module("app.app")
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()

    assert client.get("/ready").status_code == 200
    assert client.get("/visits").get_json() == {"visits": 1}
    assert client.get("/visits").get_json() == {"visits": 2}
    assert client.get("/stats").get_json() == {"total_visits": 2}

    worker.run_once()
    with psycopg.connect(DATABASE_URL) as connection:
        reports = connection.execute("SELECT count(*) FROM reports").fetchone()[0]
    assert reports == 1
