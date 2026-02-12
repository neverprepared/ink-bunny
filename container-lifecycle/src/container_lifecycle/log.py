"""Structured JSON logging via structlog."""

from __future__ import annotations

import sys
from typing import Any

import structlog


def _rename_warning_to_warn(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Rename 'warning' level to 'warn' for Node.js log compatibility."""
    if event_dict.get("level") == "warning":
        event_dict["level"] = "warn"
    return event_dict


def setup_logging() -> None:
    """Configure structlog with JSON output matching the Node.js format."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            _rename_warning_to_warn,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(
    session_name: str | None = None,
    container_name: str | None = None,
) -> structlog.stdlib.BoundLogger:
    """Return a logger optionally bound with session context."""
    logger = structlog.get_logger()
    if session_name:
        logger = logger.bind(session_name=session_name)
    if container_name:
        logger = logger.bind(container_name=container_name)
    return logger
