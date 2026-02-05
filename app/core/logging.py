from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable

import structlog


def _build_handlers(log_file_path: Path | None) -> Iterable[logging.Handler]:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file_path is not None:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file_path, encoding="utf-8"))
    return handlers


def setup_logging(level: int = logging.INFO, *, log_file_path: Path | None = None) -> None:
    handlers = list(_build_handlers(log_file_path))
    logging.basicConfig(level=level, format="%(message)s", handlers=handlers)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
