from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

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
    """Клиент OpenAI Assistants API: Threads + Runs."""

    _invalid_json_retries = 2

    def __init__(self, settings: LLMSettings, runtime: RuntimeSettings) -> None:
        if not settings.assistant_id:
            raise ValueError("LLM_ASSISTANT_ID обязателен для Assistants API")
        self._settings = settings
        self._runtime = runtime
        self._logger = logging_utils.get_logger("llm")
        self._client = OpenAI(
            api_key=settings.api_key.get_secret_value(),
            base_url=str(settings.api_url).rstrip("/"),
        )

    def infer(self, row: SourceRow) -> LLMResult:
        last_error: ValueError | None = None
        for attempt in range(self._invalid_json_retries + 1):
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
            self._logger.info("Ответ LLM получен", product_id=row.product_id)
            return LLMResult(data=data, raw_text=raw_text)

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
                return self._call_assistant(row)
        raise LLMClientError("Не удалось получить ответ от Assistants API")

    def _call_assistant(self, row: SourceRow) -> Dict[str, Any]:
        try:
            thread = self._client.beta.threads.create(
                metadata={"product_id": row.product_id},
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self._compose_prompt(row),
                            }
                        ],
                    }
                ],
            )
            run = self._client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self._settings.assistant_id,
                **({"model": self._settings.model} if self._settings.model else {}),
            )
            completed_run = self._wait_run(thread.id, run.id)
            if completed_run.status != "completed":
                error = getattr(completed_run, "last_error", None)
                raise LLMClientError(f"Run завершился со статусом {completed_run.status}: {error}")
            return self._client.beta.threads.messages.list(
                thread_id=thread.id,
                order="desc",
                limit=5,
            ).to_dict()
        except OpenAIError as exc:  # pragma: no cover - сеть
            message = getattr(exc, "message", str(exc))
            self._logger.error("Ошибка OpenAI", error=message)
            raise LLMClientError(message) from exc

    def _wait_run(self, thread_id: str, run_id: str):
        deadline = time.monotonic() + self._runtime.llm_timeout_seconds
        while True:
            run = self._client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run.status in {"completed", "failed", "cancelled", "expired"}:
                return run
            if time.monotonic() >= deadline:
                raise LLMClientError("Истек таймаут ожидания ответа Assistants")
            time.sleep(1)

    def _compose_prompt(self, row: SourceRow) -> str:
        category = row.category or "не указана"
        name_en = self._extract_name(row.raw_values, "name (en)")
        name_ru = self._extract_name(row.raw_values, "name (ru)")
        template = (
            "Категория: {category}\n"
            "Название (EN): {name_en}\n"
            "Название (RU): {name_ru}\n"
            "Описание товара:\n{content}"
        )
        return template.format(
            category=category,
            name_en=name_en,
            name_ru=name_ru,
            content=row.product_content,
        )

    @staticmethod
    def _extract_name(raw_values: Dict[str, Any], key: str) -> str:
        value = raw_values.get(key, "")
        if not isinstance(value, str):
            return "не указано"
        value = value.strip()
        return value or "не указано"

    def _extract_text(self, response_payload: Dict[str, Any]) -> str:
        messages = response_payload.get("data", [])
        for message in messages:
            if message.get("role") != "assistant":
                continue
            chunks: list[str] = []
            for content in message.get("content", []) or []:
                text_block = content.get("text")
                if isinstance(text_block, dict):
                    value = text_block.get("value")
                    if isinstance(value, str):
                        chunks.append(value)
                elif isinstance(text_block, str):
                    chunks.append(text_block)
            if chunks:
                return "".join(chunks)
        raise LLMClientError("Assistants API вернул пустое сообщение")

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *_: object) -> None:
        # клиент OpenAI не требует закрытия
        return None
