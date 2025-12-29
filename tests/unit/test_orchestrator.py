from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.config.models import (
    AppConfig,
    BrandRegistrySettings,
    GoogleAuthSettings,
    LLMSettings,
    MappingRule,
    MappingSettings,
    MappingSource,
    MappingTable,
    RuntimeSettings,
    SinkSheetSettings,
    SourceSheetSettings,
)
from app.core.mapping_engine import MappingEngine
from app.orchestrator.models import SourceRow
from app.orchestrator.service import Orchestrator
from app.services.llm_client import LLMResult


@dataclass
class FakeSource:
    rows: List[SourceRow]

    def __init__(self, rows: List[SourceRow]) -> None:
        self.rows = rows
        self.done: List[int] = []
        self.errors: List[int] = []

    def fetch_pending(self, limit: int) -> List[SourceRow]:
        return self.rows[:limit]

    def mark_done(self, row_index: int, *, note: str = "OK", llm_raw: str | None = None) -> None:
        self.done.append(row_index)

    def mark_error(self, row_index: int, note: str) -> None:
        self.errors.append(row_index)


class FakeSink:
    def __init__(self) -> None:
        self.patches: Dict[str, Dict[str, object]] = {}

    def apply_patch(self, key: str, patch: Dict[str, object]) -> None:
        self.patches[key] = patch


class FakeLLM:
    def __init__(self, response: Dict[str, object]) -> None:
        self.response = response

    def infer(self, row: SourceRow) -> LLMResult:
        return LLMResult(data=self.response, raw_text="{}")


class FakeBrandRegistry:
    def attach_brand_id(self, result: LLMResult) -> LLMResult:
        return result


def _config() -> AppConfig:
    return AppConfig(
        runtime=RuntimeSettings(
            batch_size=10,
            max_rps=2,
            max_rpm=60,
            llm_timeout_seconds=30,
            llm_max_retries=1,
            worker_id="worker-1",
        ),
        google_auth=GoogleAuthSettings(service_account_json_path="/tmp/key.json", delegated_user=None),
        source_sheet=SourceSheetSettings(
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
            in_progress_ttl_seconds=1800,
            claim_token_column="claim_token",
        ),
        sink_sheet=SinkSheetSettings(
            spreadsheet_id="sink",
            worksheet_name="ws",
            mode="upsert_by_xml_id",
            key_column="IE_XML_ID",
        ),
        llm=LLMSettings(api_url="https://example.com", api_key="dummy", model="gpt"),
        mapping=MappingSettings(path="config/mapping.yaml"),
        brand_registry=BrandRegistrySettings(
            spreadsheet_id="brands",
            worksheet_name="registry",
            name_column="brand",
            id_column="brand_id",
        ),
    )


def test_orchestrator_success_flow() -> None:
    source_row = SourceRow(
        row_index=2,
        product_id="hash123",
        product_content="desc",
        category="wine",
        image_path="img",
        claim_token=None,
        raw_values={"product_id_hash": "hash123"},
    )
    source = FakeSource(rows=[source_row])
    sink = FakeSink()
    mapping = MappingEngine(
        MappingTable(
            rules=[
                MappingRule(
                    name="xml",
                    source=MappingSource.SOURCE_ROW,
                    source_column="product_id_hash",
                    target_column="IE_XML_ID",
                ),
                MappingRule(
                    name="name",
                    source=MappingSource.JSON,
                    json_path="$.name",
                    target_column="IE_NAME",
                ),
            ]
        )
    )
    llm = FakeLLM({"name": "Test"})
    registry = FakeBrandRegistry()

    orchestrator = Orchestrator(  # type: ignore[arg-type]
        config=_config(),
        source=source,  # type: ignore[arg-type]
        sink=sink,      # type: ignore[arg-type]
        mapping_engine=mapping,
        brand_registry=registry,  # type: ignore[arg-type]
        llm_client=llm,  # type: ignore[arg-type]
    )

    orchestrator.run_once()

    assert source.done == [2]
    assert source.errors == []
    assert sink.patches["hash123"]["IE_NAME"] == "Test"


def test_orchestrator_fails_on_empty_patch() -> None:
    source_row = SourceRow(
        row_index=3,
        product_id="hash000",
        product_content="desc",
        category="wine",
        image_path="img",
        claim_token=None,
        raw_values={"product_id_hash": "hash000"},
    )
    source = FakeSource(rows=[source_row])
    sink = FakeSink()
    mapping = MappingEngine(MappingTable(rules=[]))
    llm = FakeLLM({})
    registry = FakeBrandRegistry()

    orchestrator = Orchestrator(  # type: ignore[arg-type]
        config=_config(),
        source=source,  # type: ignore[arg-type]
        sink=sink,      # type: ignore[arg-type]
        mapping_engine=mapping,
        brand_registry=registry,  # type: ignore[arg-type]
        llm_client=llm,  # type: ignore[arg-type]
    )

    orchestrator.run_once()

    assert source.done == []
    assert source.errors == [3]
    assert sink.patches == {}
