from __future__ import annotations

from app.adapters.sink_adapter import SinkSheetAdapter
from app.adapters.source_adapter import SourceSheetAdapter
from app.config.models import AppConfig
from app.core import logging as logging_utils
from app.core.mapping_engine import MappingEngine
from app.core.rate_limiter import RateLimiter
from app.services.llm_client import LLMClient


class Orchestrator:
    def __init__(
        self,
        config: AppConfig,
        source: SourceSheetAdapter,
        sink: SinkSheetAdapter,
        mapping_engine: MappingEngine,
        llm_client: LLMClient,
    ) -> None:
        self._config = config
        self._source = source
        self._sink = sink
        self._mapping_engine = mapping_engine
        self._llm = llm_client
        self._logger = logging_utils.get_logger("orchestrator")
        self._rate_limiter = RateLimiter(
            max_rps=config.runtime.max_rps,
            max_rpm=config.runtime.max_rpm,
        )

    def run_once(self) -> None:
        batch_size = self._config.runtime.batch_size
        rows = self._source.fetch_pending(batch_size)
        if not rows:
            self._logger.info("Нет строк со статусом 'Не обработано'")
            return

        success = 0
        errors = 0
        for row in rows:
            try:
                self._rate_limiter.wait()
                llm_result = self._llm.infer(row)
                patch = self._mapping_engine.build_patch(
                    llm_data=llm_result.data,
                    source_row=row,
                )
                if not patch:
                    raise RuntimeError("Нет данных для записи от агента")
                self._sink.apply_patch(row.product_id, patch)
                self._source.mark_done(row.row_index, llm_raw=llm_result.raw_text)
                success += 1
            except Exception as exc:
                errors += 1
                error_message = str(exc)
                note = self._short_error(error_message)
                self._logger.error(
                    "Ошибка обработки строки",
                    row=row.row_index,
                    product_id=row.product_id,
                    error=error_message,
                    exc_info=True,
                )
                self._source.mark_error(row.row_index, note)
                self._handle_fatal_error(error_message)

        self._logger.info(
            "Цикл обработки завершён",
            total=len(rows),
            success=success,
            errors=errors,
        )

    @staticmethod
    def _short_error(message: str, limit: int = 180) -> str:
        if len(message) <= limit:
            return message
        return f"{message[:limit - 3]}..."

    def _handle_fatal_error(self, message: str) -> None:
        if not self._should_abort(message):
            return
        exit_code = self._config.runtime.restart_exit_code
        self._logger.critical(
            "Обнаружена фатальная ошибка — завершаем процесс для рестарта контейнера",
            exit_code=exit_code,
            fatal_message=message,
        )
        raise SystemExit(exit_code)

    def _should_abort(self, message: str) -> bool:
        markers = self._config.runtime.fatal_error_markers
        if not markers:
            return False
        lowered = message.casefold()
        return any(marker.casefold() in lowered for marker in markers)
