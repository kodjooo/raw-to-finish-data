# raw-to-finished-data

raw-to-finished-data — сервис автоматической постобработки карточек каталога. Он забирает строки из Google Sheet A (источник), отправляет `product_content` и `category` в LLM (Responses API), валидирует ответ JSON, сопоставляет поля с битриксовым шаблоном по `config/mapping.yaml` и обновляет Google Sheet B. Проект изначально задуман как контейнеризированный (Docker Desktop локально, Docker Engine на сервере) и управляется через CLI `python -m app.main run`.

## Быстрый старт (Docker Desktop)

1. Скопируйте конфиг окружения и заполните его:
   ```bash
   cp .env.example .env
   # Отредактируйте .env согласно комментариям (ID таблиц, URL LLM, сервисный аккаунт)
   ```
2. Разместите JSON ключ сервисного аккаунта Google по пути, указанному в `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` (файл монтируется в контейнер read-only).
3. Получите у ML/OpenAI команды ключ (`LLM_API_KEY`) и выберите модель (`LLM_MODEL`) в OpenAI Console → Models, затем пропишите их в `.env`.
3. Сборка и проверка конфигов:
   ```bash
   docker compose build processor
   docker compose run --rm processor python -m app.main validate-config
   ```
4. Запуск основного цикла обработки (один батч за запуск):
   ```bash
   docker compose run --rm processor python -m app.main run
   ```
   Для непрерывной работы на рабочем окружении используйте `docker compose up -d processor`.

## Ключевые переменные окружения

- `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` — путь к JSON сервисного аккаунта (IAM → Service Accounts).
- `SOURCE_SPREADSHEET_ID` / `SOURCE_WORKSHEET_NAME` — таблица-источник с сырыми данными.
- `SINK_SPREADSHEET_ID` / `SINK_WORKSHEET_NAME` — таблица-приёмник (битриксовый шаблон).
- `SOURCE_STATUS_*`, `SOURCE_*_COLUMN` — колонки и статусы workflow (включая `SOURCE_STATUS_IN_PROGRESS`, `SOURCE_WORKER_COLUMN`, `SOURCE_IN_PROGRESS_AT_COLUMN`, `SOURCE_IN_PROGRESS_TTL_SECONDS`, `SOURCE_CLAIM_TOKEN_COLUMN`).
- `LLM_API_URL` (обычно `https://api.openai.com/v1`), `LLM_API_KEY` (ключ OpenAI), `LLM_MODEL` (модель из OpenAI Console → Models), `LLM_REASONING_EFFORT` (`none|low|medium|high`), `LLM_SYSTEM_PROMPT_PATH` (путь к файлу системного промпта), `LLM_USER_PROMPT_PATH` (путь к файлу пользовательского промпта), `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`.
- `BATCH_SIZE`, `MAX_RPS`, `MAX_RPM` — ограничения пайплайна.
- `CONFIG_PATH`, `MAPPING_PATH` — переопределение путей к YAML-конфига и mapping.

Все переменные задокументированы в `.env` (с комментариями, где брать доступы).

## Тесты

```bash
docker compose run --rm processor pytest
```

## Деплой на удалённый сервер (через git)

1. Убедитесь, что на сервере стоят Docker Engine + Docker Compose v2 и настроен доступ по SSH.
2. Склонируйте репозиторий и перейдите в каталог:
   ```bash
   git clone https://github.com/kodjooo/raw-to-finish-data.git raw-to-finish-data-2
   cd raw-to-finish-data-2
   ```
3. Скопируйте `.env` (со всеми секретами) и JSON ключ сервисного аккаунта Google (например, `secrets/google-credentials.json`). Никогда не коммитьте эти файлы.
4. Соберите контейнер и прогоните валидацию конфигов:
   ```bash
   docker compose pull   # если хотите использовать готовые образы, иначе build
   docker compose build processor
   docker compose run --rm processor python -m app.main validate-config
   ```
5. Запустите сервис в фоне с пересборкой:
   ```bash
   docker compose up -d processor --build
   ```
   Логи доступны через `docker compose logs -f processor`. Обновление до новой версии: `git pull`, затем `docker compose build processor && docker compose up -d --force-recreate processor`.
6. Для ручного запуска одного батча используйте `docker compose run --rm processor python -m app.main run`.
