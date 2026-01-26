from __future__ import annotations

from typing import Any, Dict, List

import pytest
from gspread.exceptions import APIError

from app.adapters.worksheet_accessor import WorksheetAccessor


class DummyResponse:
    def __init__(self, status_code: int, payload: Dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self) -> Dict[str, Any]:
        return self._payload


def _api_error(code: int) -> APIError:
    status = "UNAVAILABLE" if code == 503 else "RESOURCE_EXHAUSTED"
    if code == 500:
        status = "INTERNAL"
    payload = {"error": {"code": code, "message": "temp", "status": status}}
    return APIError(DummyResponse(code, payload))


class FakeWorksheet:
    def __init__(self) -> None:
        self._header = ["status"]
        self.batch_calls = 0

    def row_values(self, row_index: int) -> List[str]:
        if row_index == 1:
            return self._header
        return [""]

    def batch_update(self, requests: List[Dict[str, Any]]) -> None:
        self.batch_calls += 1
        if self.batch_calls <= 2:
            raise _api_error(503)

    def get_all_values(self) -> List[List[str]]:
        return [self._header]

    def append_row(self, row: List[str], value_input_option: str = "USER_ENTERED") -> None:
        return None

    def col_values(self, col_index: int) -> List[str]:
        return [self._header[0]]


def test_update_row_retries_on_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    accessor = WorksheetAccessor(FakeWorksheet())
    accessor.update_row(2, {"status": "ok"})
    assert accessor._worksheet.batch_calls == 3
