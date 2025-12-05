from app.config.models import RuntimeSettings


def test_runtime_settings_split_markers_from_string() -> None:
    settings = RuntimeSettings(
        batch_size=1,
        max_rps=1,
        max_rpm=1,
        llm_timeout_seconds=1,
        llm_max_retries=1,
        fatal_error_markers="ProxyExhaustedError; ; Playwright не может подключиться через прокси",
    )

    assert settings.fatal_error_markers == [
        "ProxyExhaustedError",
        "Playwright не может подключиться через прокси",
    ]
