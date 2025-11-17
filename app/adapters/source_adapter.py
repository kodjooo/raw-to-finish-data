from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.adapters.google_client import GoogleSheetsClient
from app.adapters.worksheet_accessor import WorksheetAccessor
from app.config.models import SourceSheetSettings
from app.core import logging as logging_utils
from app.orchestrator.models import SourceRow


class SourceSheetAdapter:
    """Отвечает за чтение строк из Google Sheet A и валидацию входных данных."""

    def __init__(self, client: GoogleSheetsClient, settings: SourceSheetSettings) -> None:
        self._client = client
        self._settings = settings
        self._logger = logging_utils.get_logger("source")
        self._accessor: Optional[WorksheetAccessor] = None

    def fetch_pending(self, limit: int) -> List[SourceRow]:
        accessor = self._get_accessor()
        pending: List[SourceRow] = []

        for row_index, row_data in accessor.fetch_rows():
            status = str(row_data.get(self._settings.status_column, ""))
            if status != self._settings.status_new:
                continue
            product_content = str(row_data.get(self._settings.content_column, "")).strip()
            product_id = str(row_data.get(self._settings.id_column, "")).strip()

            if not product_content:
                self.mark_error(row_index, "Пустой product_content")
                continue
            if not product_id:
                self.mark_error(row_index, "Пустой product_id_hash")
                continue

            pending.append(
                SourceRow(
                    row_index=row_index,
                    product_id=product_id,
                    product_content=product_content,
                    category=str(row_data.get(self._settings.category_column, "")),
                    image_path=row_data.get(self._settings.image_column),
                    raw_values=row_data,
                )
            )
            if len(pending) >= limit:
                break

        self._logger.info(
            "Загружен батч строк из источника",
            requested=limit,
            fetched=len(pending),
        )
        return pending

    def mark_error(self, row_index: int, note: str) -> None:
        updates = {
            self._settings.status_column: self._settings.status_error,
            self._settings.note_column: note,
        }
        if self._settings.llm_raw_column:
            updates[self._settings.llm_raw_column] = ""
        self._get_accessor().update_row(row_index, updates)
        self._logger.warning(
            "Строка помечена как ошибка",
            row=row_index,
            note=note,
        )

    def mark_done(self, row_index: int, *, note: str = "OK", llm_raw: str | None = None) -> None:
        updates = {
            self._settings.status_column: self._settings.status_done,
            self._settings.note_column: note,
        }
        if self._settings.processed_at_column:
            updates[self._settings.processed_at_column] = datetime.now(timezone.utc).isoformat()
        if self._settings.llm_raw_column and llm_raw is not None:
            updates[self._settings.llm_raw_column] = llm_raw
        self._get_accessor().update_row(row_index, updates)
        self._logger.info("Строка обработана", row=row_index)

    def _get_accessor(self) -> WorksheetAccessor:
        if self._accessor is None:
            worksheet = self._client.get_worksheet(
                self._settings.spreadsheet_id, self._settings.worksheet_name
            )
            self._accessor = WorksheetAccessor(worksheet)
        return self._accessor
