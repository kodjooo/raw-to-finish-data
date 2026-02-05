from __future__ import annotations

import logging
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Iterable

import structlog


def _cleanup_old_logs(log_dir: Path, *, max_age_days: int = 7) -> None:
    cutoff = datetime.now() - timedelta(days=max_age_days)
    for path in log_dir.glob("*.log*"):
        if not path.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                continue


def _build_handlers(log_file_path: Path | None) -> Iterable[logging.Handler]:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file_path is not None:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        _cleanup_old_logs(log_file_path.parent, max_age_days=7)
        handlers.append(
            TimedRotatingFileHandler(
                log_file_path,
                when="D",
                interval=1,
                backupCount=7,
                encoding="utf-8",
                utc=False,
            )
        )
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
