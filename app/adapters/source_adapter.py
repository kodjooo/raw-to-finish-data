from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import socket

from app.adapters.google_client import GoogleSheetsClient
from app.adapters.worksheet_accessor import WorksheetAccessor
from app.config.models import SourceSheetSettings
from app.core import logging as logging_utils
from app.orchestrator.models import SourceRow


class SourceSheetAdapter:
    """Отвечает за чтение строк из Google Sheet A и валидацию входных данных."""

    def __init__(
        self,
        client: GoogleSheetsClient,
        settings: SourceSheetSettings,
        *,
        worker_id: Optional[str] = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._logger = logging_utils.get_logger("source")
        self._accessor: Optional[WorksheetAccessor] = None
        self._worker_id = worker_id or socket.gethostname()

    def fetch_pending(self, limit: int) -> List[SourceRow]:
        accessor = self._get_accessor()
        pending: List[SourceRow] = []

        for row_index, row_data in accessor.fetch_rows():
            status = str(row_data.get(self._settings.status_column, ""))
            if self._is_stale_in_progress(status, row_data):
                self._release_row(row_index)
                continue
            if self._settings.status_in_progress and status == self._settings.status_in_progress:
                continue
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

            if not self._claim_row(row_index):
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
        if self._settings.worker_column:
            updates[self._settings.worker_column] = ""
        if self._settings.in_progress_at_column:
            updates[self._settings.in_progress_at_column] = ""
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

    def _claim_row(self, row_index: int) -> bool:
        if not self._settings.status_in_progress:
            return True
        updates = {
            self._settings.status_column: self._settings.status_in_progress,
        }
        if self._settings.worker_column:
            updates[self._settings.worker_column] = self._worker_id
        if self._settings.in_progress_at_column:
            updates[self._settings.in_progress_at_column] = datetime.now(timezone.utc).isoformat()
        self._get_accessor().update_row(row_index, updates)
        fresh = self._get_accessor().get_row(row_index)
        status = str(fresh.get(self._settings.status_column, ""))
        if status != self._settings.status_in_progress:
            return False
        if self._settings.worker_column:
            return str(fresh.get(self._settings.worker_column, "")).strip() == self._worker_id
        return True

    def _release_row(self, row_index: int) -> None:
        updates = {
            self._settings.status_column: self._settings.status_new,
        }
        if self._settings.worker_column:
            updates[self._settings.worker_column] = ""
        if self._settings.in_progress_at_column:
            updates[self._settings.in_progress_at_column] = ""
        self._get_accessor().update_row(row_index, updates)
        self._logger.warning("Освобождён зависший статус", row=row_index)

    def _is_stale_in_progress(self, status: str, row_data: dict) -> bool:
        if not self._settings.status_in_progress:
            return False
        if status != self._settings.status_in_progress:
            return False
        ttl = self._settings.in_progress_ttl_seconds
        if not ttl:
            return False
        raw_ts = str(row_data.get(self._settings.in_progress_at_column or "", "")).strip()
        if not raw_ts:
            return True
        try:
            started_at = datetime.fromisoformat(raw_ts)
        except ValueError:
            return True
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
        return age_seconds >= ttl
