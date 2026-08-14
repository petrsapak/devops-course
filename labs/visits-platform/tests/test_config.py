from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

from app.config import database_url


DATABASE_ENVIRONMENT_VARIABLES = (
    "DATABASE_URL",
    "DB_HOST",
    "DB_PASSWORD_FILE",
    "DB_PORT",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
    "POSTGRES_USER",
)


def clear_database_environment(monkeypatch) -> None:
    for name in DATABASE_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_explicit_database_url_is_preserved(monkeypatch):
    explicit = "postgresql://example.invalid/course"
    monkeypatch.setenv("DATABASE_URL", explicit)
    assert database_url() == explicit


def test_connection_info_escapes_special_characters(monkeypatch):
    clear_database_environment(monkeypatch)
    password = "spaces @ slashes / colons : and 'quotes'"
    monkeypatch.setenv("POSTGRES_PASSWORD", password)

    parsed = conninfo_to_dict(database_url())

    assert parsed["password"] == password
    assert parsed["host"] == "db"
    assert parsed["dbname"] == "visits"


def test_password_file_takes_precedence(monkeypatch, tmp_path: Path):
    clear_database_environment(monkeypatch)
    secret_file = tmp_path / "database-password"
    secret_file.write_text("from-secret-file\n", encoding="utf-8")
    monkeypatch.setenv("DB_PASSWORD_FILE", str(secret_file))
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-environment")

    parsed = conninfo_to_dict(database_url())

    assert parsed["password"] == "from-secret-file"
