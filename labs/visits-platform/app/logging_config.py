import json
import logging
import os
import time


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        event = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "service": self.service,
            "timestamp": int(time.time()),
        }
        for field in ("request_id", "path", "status"):
            if hasattr(record, field):
                event[field] = getattr(record, field)
        return json.dumps(event)


def configure_logging(service: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
