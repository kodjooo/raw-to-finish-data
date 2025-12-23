from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from openai import OpenAI
from openai import OpenAIError
from tenacity import (  # type: ignore[import-untyped]
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config.models import LLMSettings, RuntimeSettings
from app.core import logging as logging_utils
from app.orchestrator.models import SourceRow
from app.services.json_utils import parse_llm_payload


class LLMClientError(RuntimeError):
    """Базовая ошибка клиента LLM."""


@dataclass
class LLMResult:
    data: Dict[str, Any]
    raw_text: str


class LLMClient:
    """Клиент OpenAI Responses API."""

    _invalid_json_retries = 2

    def __init__(self, settings: LLMSettings, runtime: RuntimeSettings) -> None:
        if not settings.model:
            raise ValueError("LLM_MODEL обязателен для Responses API")
        self._settings = settings
        self._runtime = runtime
        self._logger = logging_utils.get_logger("llm")
        self._client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=str(settings.api_url).rstrip("/"),
            timeout=self._runtime.llm_timeout_seconds,
        )
        if not hasattr(self._client, "responses"):
            raise ValueError("OpenAI SDK не поддерживает Responses API; обновите пакет openai")
        self._system_prompt = self._load_system_prompt(settings.system_prompt_path)
        self._user_prompt_template = self._load_user_prompt(settings.user_prompt_path)

    def infer(self, row: SourceRow) -> LLMResult:
        last_error: ValueError | None = None
        for attempt in range(self._invalid_json_retries + 1):
            self._logger.info(
                "LLM request settings",
                product_id=row.product_id,
                model=self._settings.model,
                reasoning_effort=self._settings.reasoning_effort or "none",
            )
            payload = self._request_with_retry(row)
            raw_text = self._extract_text(payload)
            self._logger.info(
                "LLM raw response",
                product_id=row.product_id,
                raw=raw_text,
            )
            try:
                data = parse_llm_payload(raw_text, self._logger)
            except ValueError as exc:
                last_error = exc
                if attempt >= self._invalid_json_retries:
                    raise LLMClientError(str(exc)) from exc
                self._logger.warning(
                    "LLM вернул невалидный JSON, повторяем запрос",
                    product_id=row.product_id,
                    attempt=attempt + 1,
                    max_attempts=self._invalid_json_retries + 1,
                )
                continue
            formatted_raw = json.dumps(data, ensure_ascii=False, indent=2)
            self._logger.info("Ответ LLM получен", product_id=row.product_id)
            return LLMResult(data=data, raw_text=formatted_raw)

        raise LLMClientError("Не удалось распарсить ответ LLM") from last_error

    def _request_with_retry(self, row: SourceRow) -> Dict[str, Any]:
        retryer = Retrying(
            retry=retry_if_exception_type(LLMClientError),
            wait=wait_exponential(multiplier=1, min=1, max=5),
            stop=stop_after_attempt(self._runtime.llm_max_retries),
            reraise=True,
        )
        for attempt in retryer:
            with attempt:
                return self._call_response(row)
        raise LLMClientError("Не удалось получить ответ от Responses API")

    def _call_response(self, row: SourceRow) -> Any:
        try:
            return self._client.responses.create(
                model=self._settings.model,
                input=self._build_messages(row),
                **self._reasoning_payload(),
                metadata={"product_id": row.product_id},
            )
        except OpenAIError as exc:  # pragma: no cover - сеть
            message = getattr(exc, "message", str(exc))
            self._logger.error("Ошибка OpenAI", error=message)
            raise LLMClientError(message) from exc

    def _compose_prompt(self, row: SourceRow) -> str:
        category = row.category or "не указана"
        name_en = self._extract_name(row.raw_values, "name (en)")
        name_ru = self._extract_name(row.raw_values, "name (ru)")
        if not self._user_prompt_template:
            raise ValueError("Не задан шаблон пользовательского промпта")
        return self._user_prompt_template.format(
            category=category,
            name_en=name_en,
            name_ru=name_ru,
            content=row.product_content,
        )

    def _build_messages(self, row: SourceRow) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        if self._system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": self._system_prompt}],
                }
            )
        messages.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": self._compose_prompt(row)}],
            }
        )
        return messages

    @staticmethod
    def _extract_name(raw_values: Dict[str, Any], key: str) -> str:
        value = raw_values.get(key, "")
        if not isinstance(value, str):
            return "не указано"
        value = value.strip()
        return value or "не указано"

    def _extract_text(self, response_payload: Any) -> str:
        output_text = getattr(response_payload, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        payload = response_payload.to_dict() if hasattr(response_payload, "to_dict") else response_payload
        if isinstance(payload, dict):
            for output in payload.get("output", []) or []:
                if output.get("type") != "message":
                    continue
                for content in output.get("content", []) or []:
                    if content.get("type") not in {"output_text", "text"}:
                        continue
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        return text
                    if isinstance(text, dict):
                        value = text.get("value") or text.get("text")
                        if isinstance(value, str) and value.strip():
                            return value
        raise LLMClientError("Responses API вернул пустое сообщение")

    def _reasoning_payload(self) -> Dict[str, Any]:
        effort = self._settings.reasoning_effort
        if not effort or effort == "none":
            return {}
        return {"reasoning": {"effort": effort}}

    @staticmethod
    def _load_system_prompt(path: Path | None) -> str | None:
        if not path:
            return None
        if not path.exists():
            raise ValueError(f"Не найден файл системного промпта {path}")
        content = path.read_text(encoding="utf-8").strip()
        return content or None

    @staticmethod
    def _load_user_prompt(path: Path | None) -> str:
        if not path:
            raise ValueError("Не задан путь к пользовательскому промпту")
        if not path.exists():
            raise ValueError(f"Не найден файл пользовательского промпта {path}")
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError("Файл пользовательского промпта пустой")
        return content

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *_: object) -> None:
        # клиент OpenAI не требует закрытия
        return None
