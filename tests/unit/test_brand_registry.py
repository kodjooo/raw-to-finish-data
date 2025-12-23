from __future__ import annotations

from typing import List

from app.adapters.google_client import GoogleSheetsClient
from app.config.models import BrandRegistrySettings
from app.services.brand_registry import BrandRegistry
from app.services.llm_client import LLMResult


class FakeWorksheet:
    def __init__(self, rows: List[List[str]]) -> None:
        self._rows = rows

    def row_values(self, index: int) -> List[str]:
        return self._rows[index - 1] if index - 1 < len(self._rows) else []

    def get_all_values(self) -> List[List[str]]:
        return self._rows

    def append_row(self, row: List[str], value_input_option: str | None = None) -> None:
        self._rows.append(row)

    def col_values(self, col_index: int) -> List[str]:
        result: List[str] = []
        for row in self._rows:
            result.append(row[col_index - 1] if col_index - 1 < len(row) else "")
        return result


class FakeGoogleClient(GoogleSheetsClient):
    def __init__(self, worksheet: FakeWorksheet) -> None:
        self._worksheet = worksheet

    def get_worksheet(self, spreadsheet_id: str, worksheet_name: str):  # type: ignore[override]
        return self._worksheet


def _settings() -> BrandRegistrySettings:
    return BrandRegistrySettings(
        spreadsheet_id="sheet",
        worksheet_name="brands",
        name_column="brand",
        id_column="brand_id",
    )


def test_attach_brand_id_uses_existing_brand() -> None:
    worksheet = FakeWorksheet(
        [
            ["brand_id", "brand"],
            ["001", "Alpha"],
        ]
    )
    service = BrandRegistry(FakeGoogleClient(worksheet), _settings())
    result = service.attach_brand_id(LLMResult(data={"brand": "Alpha"}, raw_text="{}"))

    assert result.data["brand_id"] == "1"


def test_attach_brand_id_creates_new_brand() -> None:
    worksheet = FakeWorksheet(
        [
            ["brand_id", "brand"],
            ["2", "Beta"],
        ]
    )
    service = BrandRegistry(FakeGoogleClient(worksheet), _settings())
    result = service.attach_brand_id(LLMResult(data={"brand": "Gamma"}, raw_text="{}"))

    assert result.data["brand_id"] == "3"
    assert worksheet.get_all_values()[-1] == ["3", "Gamma"]
