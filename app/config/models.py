from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import AnyUrl, BaseModel, Field, SecretStr, field_validator, model_validator


class RuntimeSettings(BaseModel):
    batch_size: int = Field(gt=0, description="Размер батча строк-источников")
    max_rps: float = Field(gt=0, description="Лимит запросов в секунду к LLM")
    max_rpm: int = Field(gt=0, description="Лимит запросов в минуту")
    llm_timeout_seconds: int = Field(gt=0, description="Таймаут ожидания ответа LLM")
    llm_max_retries: int = Field(ge=1, description="Количество попыток при ошибках LLM")
    worker_id: Optional[str] = Field(default=None, description="Идентификатор обработчика")


class GoogleAuthSettings(BaseModel):
    service_account_json_path: Path
    delegated_user: Optional[str] = None


class SourceSheetSettings(BaseModel):
    spreadsheet_id: str
    worksheet_name: str
    status_column: str
    status_new: str
    status_in_progress: Optional[str] = None
    status_done: str
    status_error: str
    note_column: str
    content_column: str
    category_column: str
    image_column: str
    id_column: str
    processed_at_column: Optional[str] = None
    llm_raw_column: Optional[str] = None
    worker_column: Optional[str] = None
    in_progress_at_column: Optional[str] = None
    in_progress_ttl_seconds: Optional[int] = None
    claim_token_column: Optional[str] = None

    @field_validator(
        "status_in_progress",
        "processed_at_column",
        "llm_raw_column",
        "worker_column",
        "in_progress_at_column",
        "claim_token_column",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("in_progress_ttl_seconds", mode="before")
    @classmethod
    def _empty_ttl_to_none(cls, value: Optional[str | int]) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value


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
    reasoning_effort: Optional[Literal["none", "low", "medium", "high"]] = None
    system_prompt_path: Optional[Path] = None
    user_prompt_path: Optional[Path] = None

    @model_validator(mode="after")
    def _ensure_target(self) -> "LLMSettings":
        if not self.model:
            raise ValueError("Нужно задать LLM_MODEL")
        return self


class MappingSettings(BaseModel):
    path: Path


class BrandRegistrySettings(BaseModel):
    spreadsheet_id: str
    worksheet_name: str
    name_column: str
    id_column: str


class AppConfig(BaseModel):
    version: int = 1
    runtime: RuntimeSettings
    google_auth: GoogleAuthSettings
    source_sheet: SourceSheetSettings
    sink_sheet: SinkSheetSettings
    llm: LLMSettings
    mapping: MappingSettings
    brand_registry: BrandRegistrySettings

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
