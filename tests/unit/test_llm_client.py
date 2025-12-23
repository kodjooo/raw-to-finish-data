from __future__ import annotations

import types
from pathlib import Path

import pytest

from app.config.models import LLMSettings, RuntimeSettings
from app.orchestrator.models import SourceRow
from app.services.llm_client import LLMClient, LLMClientError, LLMResult


def _runtime() -> RuntimeSettings:
    return RuntimeSettings(batch_size=1, max_rps=1, max_rpm=1, llm_timeout_seconds=5, llm_max_retries=1)


def _settings() -> LLMSettings:
    return LLMSettings(
        api_url="https://example.com",
        api_key="test-key",
        model="gpt-5-nano-2025-08-07",
        reasoning_effort="low",
        user_prompt_path=Path("config/user_prompt.txt"),
    )


def _source_row() -> SourceRow:
    return SourceRow(
        row_index=1,
        product_id="pid",
        product_content="desc",
        category="wine",
        image_path=None,
        raw_values={
            "product_id_hash": "pid",
            "name (en)": "Merlot Reserve",
            "name (ru)": "Мерло Резерв",
        },
    )


def test_llm_client_retries_invalid_json(monkeypatch):
    texts = iter(["{", '{"name": "valid"}'])
    call_counter = {"count": 0}

    def fake_request(self, row):
        call_counter["count"] += 1
        return {}

    def fake_extract(self, payload):
        return next(texts)

    client = LLMClient(_settings(), _runtime())
    monkeypatch.setattr(client, "_request_with_retry", types.MethodType(fake_request, client))
    monkeypatch.setattr(client, "_extract_text", types.MethodType(fake_extract, client))

    result = client.infer(_source_row())

    assert isinstance(result, LLMResult)
    assert result.data["name"] == "valid"
    assert call_counter["count"] == 2


def test_llm_client_stops_after_max_invalid_json(monkeypatch):
    def fake_request(self, row):
        return {}

    def fake_extract(self, payload):
        return "{"

    client = LLMClient(_settings(), _runtime())
    monkeypatch.setattr(client, "_request_with_retry", types.MethodType(fake_request, client))
    monkeypatch.setattr(client, "_extract_text", types.MethodType(fake_extract, client))

    with pytest.raises(LLMClientError):
        client.infer(_source_row())


def test_compose_prompt_contains_names():
    client = LLMClient(_settings(), _runtime())
    prompt = client._compose_prompt(_source_row())

    assert "Основное изначальное название: Merlot Reserve" in prompt
    assert "Второстепенное изначальное название: Мерло Резерв" in prompt


def test_compose_prompt_uses_safe_defaults_for_names():
    client = LLMClient(_settings(), _runtime())
    row = _source_row()
    row.raw_values["name (en)"] = "   "
    row.raw_values.pop("name (ru)", None)

    prompt = client._compose_prompt(row)

    assert "Основное изначальное название: не указано" in prompt
    assert "Второстепенное изначальное название: не указано" in prompt
