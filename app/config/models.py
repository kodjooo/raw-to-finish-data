from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, List, Literal, Optional

from pydantic import AnyUrl, BaseModel, Field, SecretStr, field_validator, model_validator


class RuntimeSettings(BaseModel):
    batch_size: int = Field(gt=0, description="Размер батча строк-источников")
    max_rps: float = Field(gt=0, description="Лимит запросов в секунду к LLM")
    max_rpm: int = Field(gt=0, description="Лимит запросов в минуту")
    llm_timeout_seconds: int = Field(gt=0, description="Таймаут ожидания ответа LLM")
    llm_max_retries: int = Field(ge=1, description="Количество попыток при ошибках LLM")
    fatal_error_markers: List[str] = Field(
        default_factory=list,
        description="Подстроки фатальных ошибок, при которых сервис завершает работу",
    )
    restart_exit_code: int = Field(
        default=99,
        ge=1,
        le=255,
        description="Код выхода процесса при фатальной ошибке (для рестарта контейнера)",
    )

    @field_validator("fatal_error_markers", mode="before")
    @classmethod
    def _split_error_markers(cls, value: Any) -> Any:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            normalized = value.replace("\n", ";")
            return [item.strip() for item in normalized.split(";") if item.strip()]
        raise TypeError("fatal_error_markers ожидает список строк или строку")


class GoogleAuthSettings(BaseModel):
    service_account_json_path: Path
    delegated_user: Optional[str] = None


class SourceSheetSettings(BaseModel):
    spreadsheet_id: str
    worksheet_name: str
    status_column: str
    status_new: str
    status_done: str
    status_error: str
    note_column: str
    content_column: str
    category_column: str
    image_column: str
    id_column: str
    processed_at_column: Optional[str] = None
    llm_raw_column: Optional[str] = None


class SinkMode(str, Enum):
    APPEND = "append"
    UPSERT_BY_XML_ID = "upsert_by_xml_id"


class SinkSheetSettings(BaseModel):
    spreadsheet_id: str
    worksheet_name: str
    mode: SinkMode = SinkMode.UPSERT_BY_XML_ID
    key_column: str = Field(default="IE_XML_ID")


class LLMSettings(BaseModel):
    api_url: AnyUrl
    api_key: SecretStr
    model: Optional[str] = None
    assistant_id: Optional[str] = None

    @model_validator(mode="after")
    def _ensure_target(self) -> "LLMSettings":
        if not self.assistant_id and not self.model:
            raise ValueError("Нужно задать LLM_ASSISTANT_ID или LLM_MODEL")
        return self


class MappingSettings(BaseModel):
    path: Path


class AppConfig(BaseModel):
    version: int = 1
    runtime: RuntimeSettings
    google_auth: GoogleAuthSettings
    source_sheet: SourceSheetSettings
    sink_sheet: SinkSheetSettings
    llm: LLMSettings
    mapping: MappingSettings

    @field_validator("version")
    @classmethod
    def _check_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Поддерживается только версия конфигурации 1")
        return value


class MappingSource(str, Enum):
    JSON = "json"
    SOURCE_ROW = "source_row"
    CONST = "const"


class MappingRule(BaseModel):
    name: str
    source: MappingSource
    target_column: str
    json_path: Optional[str] = None
    source_column: Optional[str] = None
    const_value: Optional[str] = None
    transform: List[str] = Field(default_factory=list)
    write_if_empty: bool = False
    required: bool = False

    @model_validator(mode="after")
    def _validate_source(self) -> "MappingRule":
        if self.source is MappingSource.JSON and not self.json_path:
            raise ValueError("Для source=json требуется json_path")
        if self.source is MappingSource.SOURCE_ROW and not self.source_column:
            raise ValueError("Для source=source_row требуется source_column")
        if self.source is MappingSource.CONST and self.const_value is None:
            raise ValueError("Для source=const требуется const_value")
        return self


class MappingTable(BaseModel):
    rules: List[MappingRule]

    @classmethod
    def from_raw(cls, raw_rules: List[dict]) -> "MappingTable":
        return cls(rules=[MappingRule(**rule) for rule in raw_rules])
