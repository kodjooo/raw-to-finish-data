from pathlib import Path

from app.config.loader import load_app_config


def test_empty_system_prompt_path_becomes_none(tmp_path: Path) -> None:
    config_path = Path("config/config.yaml")
    env = {
        "BATCH_SIZE": "1",
        "MAX_RPS": "1",
        "MAX_RPM": "1",
        "LLM_TIMEOUT_SECONDS": "10",
        "LLM_MAX_RETRIES": "1",
        "WORKER_ID": "test-worker",
        "GOOGLE_SERVICE_ACCOUNT_JSON_PATH": "./secrets/google-credentials.json",
        "GOOGLE_DELEGATED_USER": "",
        "SOURCE_SPREADSHEET_ID": "source-sheet",
        "SOURCE_WORKSHEET_NAME": "source",
        "SOURCE_STATUS_COLUMN": "status",
        "SOURCE_STATUS_NEW": "Не обработано",
        "SOURCE_STATUS_IN_PROGRESS": "",
        "SOURCE_STATUS_DONE": "Обработано",
        "SOURCE_STATUS_ERROR": "Ошибка",
        "SOURCE_NOTE_COLUMN": "note",
        "SOURCE_CONTENT_COLUMN": "product_content",
        "SOURCE_CATEGORY_COLUMN": "category",
        "SOURCE_IMAGE_COLUMN": "image_path",
        "SOURCE_ID_COLUMN": "product_id_hash",
        "SOURCE_PROCESSED_AT_COLUMN": "",
        "SOURCE_LLM_RAW_COLUMN": "",
        "SOURCE_WORKER_COLUMN": "",
        "SOURCE_IN_PROGRESS_AT_COLUMN": "",
        "SOURCE_IN_PROGRESS_TTL_SECONDS": "",
        "SOURCE_CLAIM_TOKEN_COLUMN": "",
        "SINK_SPREADSHEET_ID": "sink-sheet",
        "SINK_WORKSHEET_NAME": "sink",
        "LLM_API_URL": "https://api.openai.com/v1",
        "LLM_API_KEY": "sk-test",
        "LLM_MODEL": "gpt-5-mini-2025-08-07",
        "LLM_REASONING_EFFORT": "none",
        "LLM_CATEGORY_PROFILE": "spirit",
        "LLM_SYSTEM_PROMPT_PATH": "",
        "LLM_USER_PROMPT_PATH": "./config/user_prompt.txt",
        "MAPPING_PATH": "./config/mapping.yaml",
        "BRAND_REGISTRY_SPREADSHEET_ID": "brands-sheet",
        "BRAND_REGISTRY_WORKSHEET_NAME": "brands",
        "BRAND_REGISTRY_NAME_COLUMN": "Название",
        "BRAND_REGISTRY_ID_COLUMN": "ID",
    }

    config = load_app_config(config_path, env=env)

    assert config.llm.system_prompt_path is None
