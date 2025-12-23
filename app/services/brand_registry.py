from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.adapters.google_client import GoogleSheetsClient
from app.adapters.worksheet_accessor import WorksheetAccessor
from app.config.models import BrandRegistrySettings
from app.core import logging as logging_utils
from app.services.llm_client import LLMResult


class BrandRegistryError(RuntimeError):
    """Ошибка работы со справочником брендов."""


@dataclass
class _BrandEntry:
    row_index: int
    brand_id: str


class BrandRegistry:
    """Обогащает LLM-ответы brand_id из отдельной Google Sheet."""

    def __init__(self, client: GoogleSheetsClient, settings: BrandRegistrySettings) -> None:
        self._client = client
        self._settings = settings
        self._logger = logging_utils.get_logger("brand_registry")
        self._accessor: Optional[WorksheetAccessor] = None

    def attach_brand_id(self, result: LLMResult) -> LLMResult:
        brand = str(result.data.get("brand", "")).strip()
        if not brand:
            return result
        entry = self._find_brand(brand)
        if entry is None:
            entry = self._create_brand(brand)
        data = dict(result.data)
        data["brand_id"] = entry.brand_id
        raw_text = json.dumps(data, ensure_ascii=False, indent=2)
        return LLMResult(data=data, raw_text=raw_text)

    def _find_brand(self, brand: str) -> _BrandEntry | None:
        accessor = self._get_accessor()
        needle = brand.strip().lower()
        for row_index, row_data in accessor.fetch_rows():
            name = str(row_data.get(self._settings.name_column, "")).strip()
            if name.lower() == needle and name:
                brand_id = self._normalize_id(row_data.get(self._settings.id_column, ""))
                if brand_id:
                    return _BrandEntry(row_index=row_index, brand_id=brand_id)
                raise BrandRegistryError(f"Пустой brand_id для бренда {brand}")
        return None

    def _create_brand(self, brand: str) -> _BrandEntry:
        accessor = self._get_accessor()
        next_id = self._next_brand_id()
        payload = {
            self._settings.id_column: next_id,
            self._settings.name_column: brand,
        }
        accessor.append_row(payload)
        self._logger.info("Добавлен новый бренд", brand=brand, brand_id=next_id)
        return _BrandEntry(row_index=-1, brand_id=next_id)

    def _next_brand_id(self) -> str:
        accessor = self._get_accessor()
        max_id = 0
        for _, row_data in accessor.fetch_rows():
            brand_id = self._normalize_id(row_data.get(self._settings.id_column, ""))
            if brand_id and brand_id.isdigit():
                max_id = max(max_id, int(brand_id))
        return str(max_id + 1 if max_id else 1)

    @staticmethod
    def _normalize_id(value: Any) -> str:
        text = str(value).strip()
        if not text:
            return ""
        if text.isdigit():
            return str(int(text))
        return text

    def _get_accessor(self) -> WorksheetAccessor:
        if self._accessor is None:
            worksheet = self._client.get_worksheet(
                self._settings.spreadsheet_id,
                self._settings.worksheet_name,
            )
            self._accessor = WorksheetAccessor(worksheet)
        return self._accessor
