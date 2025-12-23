from app.core import logging as logging_utils
from app.services.json_utils import LLMProductSchema, parse_llm_payload, unwrap_products


def test_unwrap_products_dict():
    logger = logging_utils.get_logger("test")
    payload = {"products": {"name": "A"}}
    result = unwrap_products(payload, logger)
    assert result == {"name": "A"}


def test_unwrap_products_list():
    logger = logging_utils.get_logger("test")
    payload = {"products": [{"name": "B"}, {"name": "C"}]}
    result = unwrap_products(payload, logger)
    assert result == {"name": "B"}


def test_parse_llm_payload_validates():
    logger = logging_utils.get_logger("test")
    raw = '{"name": "Wine", "vintage": 2019, "aroma": ["berry", "oak"]}'
    result = parse_llm_payload(raw, logger)
    assert result["name"] == "Wine"
    assert result["vintage"] == "2019"
    assert result["aroma"] == "berry, oak"


def test_parse_llm_payload_normalizes_grape_varieties():
    logger = logging_utils.get_logger("test")
    raw = '{"grape_varieties": "Cabernet Sauvignon, Merlot "}'
    result = parse_llm_payload(raw, logger)
    assert result["grape_varieties"] == "Cabernet Sauvignon, Merlot"
