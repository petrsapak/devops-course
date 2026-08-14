import os
import socket
import time
import uuid

import psycopg
from flask import Flask, Response, g, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

from app.config import database_url
from app.logging_config import configure_logging


REQUESTS = Counter(
    "app_requests_total",
    "HTTP requests handled by the visits API.",
    ["path", "status"],
)
LATENCY = Histogram(
    "app_request_seconds",
    "HTTP request duration in seconds.",
    ["path"],
)


def _feature_enabled(name: str) -> bool:
    return os.getenv(name, "false").lower() in {"1", "true", "yes", "on"}


def _metrics_payload() -> bytes:
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()


def create_app() -> Flask:
    configure_logging("visits-api")
    app = Flask(__name__)

    @app.before_request
    def begin_request() -> None:
        g.started_at = time.monotonic()
        g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    @app.after_request
    def observe(response: Response) -> Response:
        path = request.url_rule.rule if request.url_rule else "unmatched"
        LATENCY.labels(path).observe(time.monotonic() - g.started_at)
        REQUESTS.labels(path, str(response.status_code)).inc()
        response.headers["X-Request-ID"] = g.request_id
        app.logger.info(
            "request complete",
            extra={
                "request_id": g.request_id,
                "path": path,
                "status": response.status_code,
            },
        )
        return response

    @app.get("/")
    def index() -> Response:
        return jsonify(
            message="Hello from the DevOps course",
            host=socket.gethostname(),
            version=os.getenv("APP_VERSION", "dev"),
        )

    @app.get("/health")
    def health() -> Response:
        return jsonify(status="ok")

    @app.get("/ready")
    def ready() -> tuple[Response, int] | Response:
        try:
            with psycopg.connect(database_url(), connect_timeout=2) as connection:
                connection.execute("SELECT 1")
            return jsonify(status="ready")
        except psycopg.Error:
            app.logger.exception("database readiness check failed")
            return jsonify(status="not-ready"), 503

    @app.get("/visits")
    def visits() -> Response:
        with psycopg.connect(database_url()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS visits("
                    "at timestamptz DEFAULT now())"
                )
                cursor.execute("INSERT INTO visits DEFAULT VALUES")
                cursor.execute("SELECT count(*) FROM visits")
                count = cursor.fetchone()[0]
        return jsonify(visits=count)

    @app.get("/stats")
    def stats() -> tuple[Response, int] | Response:
        if not _feature_enabled("FEATURE_STATS"):
            return jsonify(error="feature-disabled"), 404
        with psycopg.connect(database_url()) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS visits("
                "at timestamptz DEFAULT now())"
            )
            count = connection.execute("SELECT count(*) FROM visits").fetchone()[0]
        return jsonify(total_visits=count)

    @app.get("/metrics")
    def metrics() -> Response:
        return Response(_metrics_payload(), content_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
