from __future__ import annotations

import types

import pytest

from app.config.models import LLMSettings, RuntimeSettings
from app.orchestrator.models import SourceRow
from app.services.llm_client import LLMClient, LLMClientError, LLMResult


def _runtime() -> RuntimeSettings:
    return RuntimeSettings(batch_size=1, max_rps=1, max_rpm=1, llm_timeout_seconds=5, llm_max_retries=1)


def _settings() -> LLMSettings:
    return LLMSettings(api_url="https://example.com", api_key="test-key", assistant_id="asst_123")


def _source_row() -> SourceRow:
    return SourceRow(
        row_index=1,
        product_id="pid",
        product_content="desc",
        category="wine",
        image_path=None,
        raw_values={"product_id_hash": "pid"},
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
