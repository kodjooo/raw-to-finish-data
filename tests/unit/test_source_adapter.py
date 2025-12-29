from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.adapters.source_adapter import SourceSheetAdapter
from app.config.models import SourceSheetSettings
from app.orchestrator.models import SourceRow


class FakeAccessor:
    def __init__(self, rows):
        self.rows = rows
        self.updated = []

    def fetch_rows(self):
        return list(self.rows)

    def update_row(self, row_index, values):
        self.updated.append((row_index, values))
        for idx, (row, data) in enumerate(self.rows):
            if row == row_index:
                data.update(values)
                break

    def get_row(self, row_index):
        for row, data in self.rows:
            if row == row_index:
                return dict(data)
        return {}


def _settings():
    return SourceSheetSettings(
        spreadsheet_id="src",
        worksheet_name="ws",
        status_column="status",
        status_new="Не обработано",
        status_in_progress="В обработке",
        status_done="Обработано",
        status_error="Ошибка",
        note_column="note",
        content_column="product_content",
        category_column="category",
        image_column="image_path",
        id_column="product_id_hash",
        processed_at_column="processed_at",
        llm_raw_column="llm_raw",
        worker_column="worker_id",
        in_progress_at_column="in_progress_at",
        in_progress_ttl_seconds=60,
    )


def test_fetch_pending_claims_row():
    rows = [
        (
            2,
            {
                "status": "Не обработано",
                "product_content": "text",
                "product_id_hash": "pid",
                "category": "wine",
                "image_path": "img.jpg",
            },
        )
    ]
    accessor = FakeAccessor(rows)
    adapter = SourceSheetAdapter.__new__(SourceSheetAdapter)
    adapter._settings = _settings()
    adapter._accessor = accessor
    adapter._worker_id = "worker-1"

    pending = adapter.fetch_pending(10)

    assert len(pending) == 1
    assert pending[0].product_id == "pid"
    assert accessor.get_row(2)["status"] == "В обработке"
    assert accessor.get_row(2)["worker_id"] == "worker-1"


def test_fetch_pending_releases_stale_row():
    stale = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    rows = [
        (
            2,
            {
                "status": "В обработке",
                "in_progress_at": stale,
                "product_content": "text",
                "product_id_hash": "pid",
                "category": "wine",
            },
        )
    ]
    accessor = FakeAccessor(rows)
    adapter = SourceSheetAdapter.__new__(SourceSheetAdapter)
    adapter._settings = _settings()
    adapter._accessor = accessor
    adapter._worker_id = "worker-1"

    pending = adapter.fetch_pending(10)

    assert pending == []
    assert accessor.get_row(2)["status"] == "Не обработано"
