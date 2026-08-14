from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from app import gunicorn_config


def test_on_starting_clears_stale_metric_files(monkeypatch, tmp_path: Path):
    stale_file = tmp_path / "counter_123.db"
    stale_file.write_text("stale", encoding="utf-8")
    unrelated_file = tmp_path / "keep.txt"
    unrelated_file.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))

    gunicorn_config.on_starting(None)

    assert not stale_file.exists()
    assert unrelated_file.exists()


def test_child_exit_marks_worker_dead(monkeypatch):
    mark_process_dead = MagicMock()
    monkeypatch.setattr(
        gunicorn_config.multiprocess,
        "mark_process_dead",
        mark_process_dead,
    )

    gunicorn_config.child_exit(None, SimpleNamespace(pid=1234))

    mark_process_dead.assert_called_once_with(1234)
