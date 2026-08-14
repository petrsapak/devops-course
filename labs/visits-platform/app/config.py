import os
from pathlib import Path

from psycopg.conninfo import make_conninfo


def _read_secret(path: str | None, fallback: str = "") -> str:
    if path and Path(path).is_file():
        return Path(path).read_text(encoding="utf-8").strip()
    return fallback


def database_url() -> str:
    if explicit := os.getenv("DATABASE_URL"):
        return explicit
    password = _read_secret(
        os.getenv("DB_PASSWORD_FILE"),
        os.getenv("POSTGRES_PASSWORD", "local-development-only"),
    )
    return make_conninfo(
        host=os.getenv("DB_HOST", "db"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "visits"),
        user=os.getenv("POSTGRES_USER", "visits"),
        password=password,
    )
