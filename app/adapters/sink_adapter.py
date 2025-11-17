from __future__ import annotations

from typing import Dict

from app.adapters.google_client import GoogleSheetsClient
from app.adapters.worksheet_accessor import WorksheetAccessor
from app.config.models import SinkMode, SinkSheetSettings
from app.core import logging as logging_utils


class SinkSheetAdapter:
    """Работает с Google Sheet B (битриксовый шаблон)."""

    def __init__(self, client: GoogleSheetsClient, settings: SinkSheetSettings) -> None:
        self._client = client
        self._settings = settings
        self._logger = logging_utils.get_logger("sink")

    def apply_patch(self, key: str, patch: Dict[str, object]) -> None:
        worksheet = self._client.get_worksheet(
            self._settings.spreadsheet_id, self._settings.worksheet_name
        )
        accessor = WorksheetAccessor(worksheet)

        if self._settings.mode is SinkMode.APPEND:
            payload = {self._settings.key_column: key}
            payload.update(patch)
            accessor.append_row(payload)
            self._logger.info("Добавлена новая строка в приёмнике", key=key)
            return

        row_index = accessor.find_row_by_column(self._settings.key_column, key)
        if row_index is None:
            payload = {self._settings.key_column: key}
            payload.update(patch)
            accessor.append_row(payload)
            self._logger.info("Создана новая строка (upsert)", key=key)
            return

        accessor.update_row(row_index, patch)
        self._logger.info("Обновлена существующая строка", key=key, row=row_index)
