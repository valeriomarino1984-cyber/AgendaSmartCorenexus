"""Log strutturati (JSON in staging/produzione) con request_id propagato via contextvars."""

from __future__ import annotations

import logging

import structlog
from structlog.typing import Processor


def configure_logging(*, level: str = "INFO", json_logs: bool = True, cache: bool = True) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=cache,
    )
    renderer: Processor = (
        structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer()
    )
    final: list[Processor] = [structlog.stdlib.ProcessorFormatter.remove_processors_meta]
    if json_logs:
        final.append(structlog.processors.format_exc_info)
    final.append(renderer)
    formatter = structlog.stdlib.ProcessorFormatter(foreign_pre_chain=shared, processors=final)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    # Il log di accesso di uvicorn contiene il path grezzo (che può includere token):
    # lo sostituisce RequestContextMiddleware, che registra solo il template della rotta.
    logging.getLogger("uvicorn.access").handlers = []
    logging.getLogger("uvicorn.access").propagate = False
