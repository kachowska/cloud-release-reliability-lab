"""Minimal structured logging without a third-party runtime dependency."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_FIELDS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"), sort_keys=True)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON handler once and keep library logging noise contained."""
    root = logging.getLogger()
    if any(getattr(handler, "_release_json_handler", False) for handler in root.handlers):
        root.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler._release_json_handler = True  # type: ignore[attr-defined]
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

