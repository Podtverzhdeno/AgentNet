"""Lightweight observability helpers used by the skeleton.

The full observability stack (OpenTelemetry, Prometheus, LangSmith, Loki)
is described in ``docs/modules/observability.md``. For the Phase 1
skeleton we just expose a configured :mod:`structlog` logger.
"""

from __future__ import annotations

import logging
from typing import Any

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Idempotently configure structlog + stdlib logging.

    ``run_session`` calls this once per process unless logging has already
    been configured by the caller.
    """

    if structlog.is_configured():
        return

    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger. Auto-configures on first use."""

    configure_logging()
    return structlog.get_logger(name)


__all__ = ["configure_logging", "get_logger"]
