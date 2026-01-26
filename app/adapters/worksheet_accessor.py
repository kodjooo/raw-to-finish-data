from __future__ import annotations

import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar

import gspread
from gspread.utils import rowcol_to_a1

from gspread.exceptions import APIError

_T = TypeVar("_T")
_RETRY_DELAYS_SECONDS = (10, 30, 60)


class WorksheetAccessor:
    """Утилита для работы с worksheet: чтение строк и обновление ячеек."""

    def __init__(self, worksheet: gspread.Worksheet) -> None:
        self._worksheet = worksheet
        self._header_row: List[str] | None = None
        self._column_map: Dict[str, int] = {}

    def header(self) -> List[str]:
        if self._header_row is None:
            self._header_row = self._with_retry(
                lambda: self._worksheet.row_values(1)
            )
            self._column_map = {
                name: idx + 1 for idx, name in enumerate(self._header_row)
            }
        return self._header_row

    def column_index(self, column_name: str) -> int:
        header = self.header()
        if column_name not in self._column_map:
            raise KeyError(
                f"Колонка '{column_name}' отсутствует. Доступные: {', '.join(header)}"
            )
        return self._column_map[column_name]

    def fetch_rows(self) -> Iterable[Tuple[int, Dict[str, Any]]]:
        values = self._with_retry(lambda: self._worksheet.get_all_values())
        if not values:
            return []
        header = values[0]
        rows: List[Tuple[int, Dict[str, Any]]] = []
        for offset, row_values in enumerate(values[1:], start=2):
            row_dict: Dict[str, Any] = {}
            for idx, column_name in enumerate(header):
                row_dict[column_name] = row_values[idx] if idx < len(row_values) else ""
            rows.append((offset, row_dict))
        return rows

    def get_row(self, row_index: int) -> Dict[str, Any]:
        header = self.header()
        row_values = self._with_retry(lambda: self._worksheet.row_values(row_index))
        row_dict: Dict[str, Any] = {}
        for idx, column_name in enumerate(header):
            row_dict[column_name] = row_values[idx] if idx < len(row_values) else ""
        return row_dict

    def update_row(self, row_index: int, values: Dict[str, Any]) -> None:
        requests = []
        for column_name, cell_value in values.items():
            col_index = self.column_index(column_name)
            cell_range = rowcol_to_a1(row_index, col_index)
            requests.append({"range": cell_range, "values": [[cell_value]]})
        if requests:
            self._with_retry(lambda: self._worksheet.batch_update(requests))

    def append_row(self, values: Dict[str, Any]) -> None:
        header = self.header()
        row = [values.get(column, "") for column in header]
        self._with_retry(
            lambda: self._worksheet.append_row(row, value_input_option="USER_ENTERED")
        )

    def find_row_by_column(self, column_name: str, needle: Any) -> Optional[int]:
        col_index = self.column_index(column_name)
        values = self._with_retry(lambda: self._worksheet.col_values(col_index))
        needle_str = str(needle).strip()
        for offset, cell_value in enumerate(values[1:], start=2):
            if str(cell_value).strip() == needle_str:
                return offset
        return None

    def _with_retry(self, action: Callable[[], _T]) -> _T:
        for attempt, delay in enumerate((0,) + _RETRY_DELAYS_SECONDS):
            if delay:
                time.sleep(delay)
            try:
                return action()
            except APIError as exc:
                if not self._is_retryable_api_error(exc):
                    raise
                if attempt >= len(_RETRY_DELAYS_SECONDS):
                    raise
        raise RuntimeError("Не удалось выполнить запрос Google Sheets после ретраев.")

    @staticmethod
    def _is_retryable_api_error(exc: APIError) -> bool:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        payload: Dict[str, Any] = {}
        if response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = {}
        error_payload = payload.get("error", payload) if isinstance(payload, dict) else {}
        code = error_payload.get("code") or status_code
        return code in (429, 500, 503)
