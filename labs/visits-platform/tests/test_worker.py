from unittest.mock import MagicMock

from app import worker


def test_run_once_records_a_report(monkeypatch):
    connection = MagicMock()
    connection.__enter__.return_value = connection
    monkeypatch.setattr(worker.psycopg, "connect", lambda *args, **kwargs: connection)
    increment = MagicMock()
    monkeypatch.setattr(worker.REPORTS, "inc", increment)

    worker.run_once()

    queries = [call.args[0] for call in connection.execute.call_args_list]
    assert "INSERT INTO reports DEFAULT VALUES" in queries
    increment.assert_called_once_with()
