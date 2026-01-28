from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from typing import Optional

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def set_correlation_id(value: Optional[str] = None) -> str:
    """Set a correlation ID for the current context and return it."""
    cid = value or str(uuid.uuid4())
    _correlation_id.set(cid)
    return cid


class CorrelationIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = _correlation_id.get()
        return True


def get_logger(name: str = "flexiflow", level: int = logging.INFO) -> logging.Logger:
    """Return a logger configured with a correlation-id filter and sane handler behavior."""
    logger = logging.getLogger(name)

    # Avoid duplicated handlers if called multiple times.
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - cid=%(correlation_id)s - %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(CorrelationIdFilter())
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger
