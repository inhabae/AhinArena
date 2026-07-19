"""Small, dependency-free helpers for correlated structured application logs."""

import contextvars
import json
import logging
from datetime import datetime, timezone


request_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def get_structured_logger(name: str) -> logging.Logger:
    """Return an isolated logger whose telemetry lines are valid JSON objects."""
    logger = logging.getLogger(f"ahinarena.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def get_request_id() -> str | None:
    return request_id_context.get()


def log_event(logger: logging.Logger, event: str, /, level: int = logging.INFO, **fields) -> None:
    """Emit one JSON log line without relying on a deployment-specific formatter."""
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        **fields,
    }
    request_id = get_request_id()
    if request_id is not None:
        payload["request_id"] = request_id
    logger.log(level, json.dumps(payload, default=str, separators=(",", ":")))
