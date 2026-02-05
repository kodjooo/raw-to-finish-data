from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import typer

from app.adapters.google_client import GoogleSheetsClient
from app.adapters.sink_adapter import SinkSheetAdapter
from app.adapters.source_adapter import SourceSheetAdapter
from app.config.loader import load_app_config, load_mapping
from app.core import logging as logging_utils
from app.core.mapping_engine import MappingEngine
from app.orchestrator.service import Orchestrator
from app.services.brand_registry import BrandRegistry
from app.services.llm_client import LLMClient

app = typer.Typer(help="CLI для сервиса структурирования товарных данных")


def _default_config_path(path: Optional[Path]) -> Path:
    if path is not None:
        return path
    env_path = os.getenv("CONFIG_PATH", "./config/config.yaml")
    return Path(env_path)


def _default_mapping_path(path: Optional[Path]) -> Path:
    if path is not None:
        return path
    env_path = os.getenv("MAPPING_PATH", "./config/mapping.yaml")
    return Path(env_path)


def _resolve_log_level() -> int:
    level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, level, logging.INFO)


def _resolve_log_file_path() -> Optional[Path]:
    raw_path = os.getenv("LOG_FILE_PATH", "").strip()
    if not raw_path:
        return None
    return Path(raw_path)


@app.command()
def validate_config(
    config_path: Optional[Path] = typer.Option(None, help="Путь к config.yaml"),
    mapping_path: Optional[Path] = typer.Option(None, help="Путь к mapping.yaml"),
) -> None:
    """Проверить, что конфиги корректно собираются."""

    logging_utils.setup_logging(_resolve_log_level(), log_file_path=_resolve_log_file_path())
    logger = logging_utils.get_logger("config")
    resolved_config = _default_config_path(config_path)
    resolved_mapping = _default_mapping_path(mapping_path)

    config = load_app_config(resolved_config)
    mapping = load_mapping(resolved_mapping)

    logger.info(
        "Конфиги валидны",
        batch_size=config.runtime.batch_size,
        mapping_rules=len(mapping.rules),
    )


@app.command()
def run(
    config_path: Optional[Path] = typer.Option(None, help="Путь к config.yaml"),
    mapping_path: Optional[Path] = typer.Option(None, help="Путь к mapping.yaml"),
) -> None:
    """Запуск основного пайплайна обработки одного батча."""

    logging_utils.setup_logging(_resolve_log_level(), log_file_path=_resolve_log_file_path())
    logger = logging_utils.get_logger("bootstrap")
    config = load_app_config(_default_config_path(config_path))
    mapping = load_mapping(_default_mapping_path(mapping_path))

    google_client = GoogleSheetsClient(
        credentials_path=config.google_auth.service_account_json_path,
        delegated_user=config.google_auth.delegated_user or None,
    )
    source_adapter = SourceSheetAdapter(
        google_client,
        config.source_sheet,
        worker_id=config.runtime.worker_id,
    )
    sink_adapter = SinkSheetAdapter(google_client, config.sink_sheet)
    mapping_engine = MappingEngine(mapping)
    brand_registry = BrandRegistry(google_client, config.brand_registry)

    with LLMClient(config.llm, config.runtime) as llm_client:
        orchestrator = Orchestrator(
            config=config,
            source=source_adapter,
            sink=sink_adapter,
            mapping_engine=mapping_engine,
            brand_registry=brand_registry,
            llm_client=llm_client,
        )
        orchestrator.run_once()

    logger.info("Цикл обработки завершён")


if __name__ == "__main__":
    app()
