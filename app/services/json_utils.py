from __future__ import annotations

import json
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, field_validator


class LLMProductSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    brand: str | None = None
    country: str | None = None
    region: str | None = None
    grape_varieties: list[str] | None = None
    sugar: str | None = None
    volume: str | None = None
    abv: str | None = None
    vintage: str | None = None
    aroma: str | None = None
    taste: str | None = None
    classification: str | None = None
    description_html: str | None = None
    section_path: str | None = None
    section_name: str | None = None
    section_code: str | None = None
    prices: Dict[str, Any] | None = None
    stocks: Dict[str, Any] | None = None

    @field_validator("grape_varieties", mode="before")
    @classmethod
    def _normalize_grape_varieties(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return items or None
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("aroma", "taste", mode="before")
    @classmethod
    def _join_list_fields(cls, value: Any) -> Any:
        if isinstance(value, list):
            return ", ".join(str(item) for item in value if item)
        return value

    @field_validator("vintage", "volume", "abv", mode="before")
    @classmethod
    def _convert_numeric_fields(cls, value: Any) -> Any:
        if isinstance(value, (int, float)):
            return str(value)
        return value


_UNWRAP_KEYS = ("products", "items", "data", "product", "payload", "result", "output")


def _first_dict_from_list(value: list[Any], logger) -> Dict[str, Any]:
    for item in value:
        if isinstance(item, dict):
            logger.warning(
                "В массиве обнаружен объект, используем его",
                keys=list(item.keys()),
            )
            return item
    raise ValueError("Массив не содержит словарей с данными товара")


def unwrap_products(payload: Dict[str, Any], logger) -> Dict[str, Any]:
    current: Any = payload
    while isinstance(current, dict):
        next_value: Any | None = None
        for key in _UNWRAP_KEYS:
            if key not in current:
                continue
            value = current[key]
            if isinstance(value, dict):
                logger.warning("Распаковываем вложенный объект", key=key, type="dict")
                next_value = value
                break
            if isinstance(value, list):
                logger.warning("Распаковываем вложенный объект", key=key, type="list")
                next_value = _first_dict_from_list(value, logger)
                break
        if next_value is None:
            return current
        current = next_value

    if isinstance(current, list):
        return _first_dict_from_list(current, logger)

    raise ValueError("Не удалось распаковать JSON: отсутствует словарь с данными товара")


def parse_llm_payload(raw_text: str, logger) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM вернул невалидный JSON") from exc

    if isinstance(parsed, dict):
        candidate = unwrap_products(parsed, logger)
        schema = LLMProductSchema.model_validate(candidate)
        return schema.model_dump(exclude_none=True)

    raise ValueError("Ответ LLM должен быть JSON-объектом")
