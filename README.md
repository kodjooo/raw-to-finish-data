# raw-to-finished-data

Контейнеризованный сервис обрабатывает сырые описания товаров из Google Sheet A, вызывает LLM по API, преобразует ответ с помощью mapping.yaml и записывает результат в битриксовую таблицу-приёмник (Google Sheet B). Единственный способ запуска — через Docker Desktop / docker compose.

## Быстрый старт (Docker Desktop)

1. Скопируйте конфиг окружения и заполните его:
   ```bash
   cp .env.example .env
   # Отредактируйте .env согласно комментариям (ID таблиц, URL LLM, сервисный аккаунт)
   ```
2. Разместите JSON ключ сервисного аккаунта Google по пути, указанному в `GOOGLE_SERVICE_ACCOUNT_JSON_PATH` (файл монтируется в контейнер read-only).
3. Получите у ML/OpenAI команды ключ (`LLM_API_KEY`) и `LLM_ASSISTANT_ID` (ID ассистента в OpenAI Assistants) и пропишите их в `.env`.
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
- `SOURCE_STATUS_*`, `SOURCE_*_COLUMN` — колонки и статусы workflow.
- `LLM_API_URL` (обычно `https://api.openai.com/v1`), `LLM_API_KEY` (ключ OpenAI), `LLM_ASSISTANT_ID` (предпочтительно), опционально `LLM_MODEL` (если ассистент не используется), `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`.
- `BATCH_SIZE`, `MAX_RPS`, `MAX_RPM` — ограничения пайплайна.
- `CONFIG_PATH`, `MAPPING_PATH` — переопределение путей к YAML-конфига и mapping.

Все переменные задокументированы в `.env` (с комментариями, где брать доступы).

## Тесты

```bash
docker compose run --rm processor pytest
```

## Деплой на удалённый сервер

1. На сервере должны быть установлены Docker Engine и Docker Compose v2.
2. Скопируйте репозиторий (или архив из CI) и `.env`/service-account JSON в нужные каталоги.
3. Выполните `docker compose build processor && docker compose up -d processor`.
4. Логи и метрики доступны через `docker compose logs -f processor`. Для обновления конфигураций перезапустите сервис (`docker compose up -d --force-recreate processor`).
