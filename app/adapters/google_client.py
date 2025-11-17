from __future__ import annotations

from pathlib import Path
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)


class GoogleSheetsClient:
    """Инкапсулирует работу с gspread и сервисным аккаунтом."""

    def __init__(
        self,
        *,
        credentials_path: Path,
        delegated_user: Optional[str] = None,
        gspread_client: Optional[gspread.Client] = None,
    ) -> None:
        self._credentials_path = credentials_path
        self._delegated_user = delegated_user
        self._gspread_client = gspread_client or self._build_client()

    def _build_client(self) -> gspread.Client:
        if not self._credentials_path.exists():
            raise FileNotFoundError(
                f"Не найден файл сервисного аккаунта {self._credentials_path}"
            )
        credentials = Credentials.from_service_account_file(
            str(self._credentials_path), scopes=GOOGLE_SCOPES
        )
        if self._delegated_user:
            credentials = credentials.with_subject(self._delegated_user)
        return gspread.authorize(credentials)

    def get_worksheet(self, spreadsheet_id: str, worksheet_name: str) -> gspread.Worksheet:
        spreadsheet = self._gspread_client.open_by_key(spreadsheet_id)
        return spreadsheet.worksheet(worksheet_name)
