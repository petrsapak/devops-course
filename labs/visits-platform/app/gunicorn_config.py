import os
from pathlib import Path

from prometheus_client import multiprocess


def on_starting(server) -> None:
    metrics_directory = Path(os.environ["PROMETHEUS_MULTIPROC_DIR"])
    metrics_directory.mkdir(parents=True, exist_ok=True)
    for database_file in metrics_directory.glob("*.db"):
        database_file.unlink()


def child_exit(server, worker) -> None:
    multiprocess.mark_process_dead(worker.pid)
