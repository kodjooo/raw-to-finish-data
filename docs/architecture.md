АРХИТЕКТУРНОЕ ОПИСАНИЕ СЕРВИСА RAW-TO-FINISHED-DATA

1. Общий обзор
   - Приложение представляет собой контейнеризованный Python-сервис, запускаемый ТОЛЬКО внутри Docker Desktop (см. Dockerfile). Вне контейнера код не исполняем.
   - Основные компоненты:
     • CLI (`app/cli.py`) — единая точка входа с командами `run` и `validate-config`; используется в `app/main.py`.
     • Orchestrator (`app/orchestrator/service.py`) запускает цикл: читает батч, вызывает LLM, применяет mapping, записывает в приёмник и обновляет статусы источника.
     • Source Adapter (`app/adapters/source_adapter.py`) — читает строки со статусом status_new через `GoogleSheetsClient` и `WorksheetAccessor`, помечает их как status_in_progress (если настроено) и сохраняет claim_token/worker_id, нормализует их в DTO `SourceRow`, сразу помечая пустые product_content / product_id_hash ошибками; зависшие строки в статусе «В обработке» возвращаются в «Не обработано» по TTL. Все колонки и статус «В обработке» опциональны — при пустых значениях в `.env` блок захвата/TTL отключается.
     • LLM Client (`app/services/llm_client.py`) — интеграция с OpenAI Responses API (официальный Python SDK + tenacity), формирует промпт из `product_content`, `category`, а также исходных колонок `name (en)`/`name (ru)` (с безопасными значениями по умолчанию), явно перечисляя требуемые ключи ответа (section_path/section_name/section_code, description_html, volume, abv, prices.retail и др.) и правила валидного JSON (экранирование кавычек, отсутствие сырых переносов), повторяет запросы согласно `llm_max_retries`, сохраняет очищенное `llm_raw` (JSON без повторяющихся ключей, сериализованный в многострочном виде) и перед записью удаляет поле `vivino_score`, если в `product_content` нет упоминания «vivino», а также в случае невалидного JSON перепрашивает модель ещё два раза, прежде чем вернуть ошибку. При необходимости можно передать режим рассуждений через `LLM_REASONING_EFFORT`.
     • Brand Registry (`app/services/brand_registry.py`) — сервис, который использует отдельный Google Sheet для хранения брендов и их ID без ведущих нулей: ищет бренд без учёта регистра, при отсутствии находит первую сверху строку с пустым названием и уже заданным ID, записывает туда бренд и возвращает этот ID; если свободного слота нет — поднимает ошибку. Обогащает результат LLM полем `brand_id` и гарантирует, что он попадёт и в `llm_raw`, и в колонку `Бренд [BRANDS] {IP_PROP1121}`.
     • Mapping Engine (`app/core/mapping_engine.py`) — слой трансформации, который, опираясь на mapping.yaml, собирает патч target_column → value, применяет трансформации (strip/join/number/extract_price/comma_to_dot/dot_to_comma/to_string/append_percent/append_liters_suffix/strip_percent/format_price/normalize_slash_path/max_price/prepend_images_path) и уважает write_if_empty; правило для IP_PROP1006 (галерея) специально исключено, чтобы поле всегда оставалось пустым, IE_DETAIL_TEXT_TYPE всегда проставляется константой "text", колонки складских остатков (`ICAT_STORE*_AMOUNT`) удалены из патча, а новые правила mapping учитывают резервные поля агента (`description`, `category_path`, `category`, `category_slug`, `volume_l`, `alcohol_percent`, `vivino_score`, `appellation`, `producer`, `classifier`, `aging`, `technical_features`, `terroir` и др.), конвертируют значения объёма/крепости в формат `0.75 л` / `13.5 %`, заполняют `IE_SECTION_PATH` (с fallback на `category_path`) и `ISECT_NAME`/`ISECT_CODE` (через `category` и `category_slug`), а цена пишется только в `ICAT_PRICE5_PRICE` как максимум из `price (without discount)` и `price (with discount)`.
     • Sink Adapter (`app/adapters/sink_adapter.py`) — клиент Google Sheet B (битриксовый формат) с режимами append/upsert_by_xml_id, обновляет только изменённые колонки и гарантированно прокидывает image_path.
     • Config Layer (`app/config/models.py`, `app/config/loader.py`) — валидирует .env/.env.example, config.yaml и mapping-файл, предоставляет типизированные объекты остальным модулям.
     • Observability — логирование (structured logs), учёт статусов/метрик и сохранение ошибок в note.

2. Поток данных
   1) Orchestrator запрашивает батч в Source Adapter с учётом лимитов (config.batch_size).
   2) Для каждой валидной строки формируется payload в LLM Client (product_content, category, при необходимости product_url/source_site); перед вызовом действует `RateLimiter` (max_rps/max_rpm из runtime).
   3) LLM Client выполняет запрос с ретраями и возвращает объект, валидированный pydantic-моделью; при ошибках возвращается техническое исключение.
   4) Brand Registry проверяет поле `brand`: если оно есть, ищет/создаёт запись в отдельной таблице и добавляет `brand_id` в JSON/`llm_raw`. При отсутствии бренда шаг пропускается.
   5) Mapping Engine инициализируется правилом из mapping-файла: извлекает значения (json/source_row/const), применяет трансформации, строит патч target_column → value, соблюдая правило «не пишем пустые значения».
   6) Sink Adapter пишет патч в Google Sheet B:
        - append — вставка новой строки, остальные поля пустые;
        - upsert_by_xml_id — поиск по IE_XML_ID = product_id_hash и обновление только перечисленных колонок.
      image_path всегда прокидывается напрямую (без скачивания/перезаписи).
   7) По результату Sink Adapter возвращает статус записи; Orchestrator обновляет строку источника (status_done/status_error, processed_at, note) через Source Adapter.

3. Конфигурация и секреты
   - `.env` / `.env.example`: лежат в корне, содержат полный список переменных (см. ниже) и комментарии, где брать доступы. Эти файлы читает Docker/`pydantic-settings`.
     • `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`, `GOOGLE_DELEGATED_USER`.
     • `SOURCE_*`, `SINK_*` — параметры листов и колонок, в том числе `SOURCE_STATUS_IN_PROGRESS`, `SOURCE_WORKER_COLUMN`, `SOURCE_IN_PROGRESS_AT_COLUMN`, `SOURCE_IN_PROGRESS_TTL_SECONDS`, `SOURCE_CLAIM_TOKEN_COLUMN` (могут быть пустыми — тогда многопоточность/claim отключены).
     • `BRAND_REGISTRY_*` — Google Sheet для справочника брендов (ID таблицы, лист, названия колонок с именем и ID).
     • `LLM_*` — настройки OpenAI Responses API; `LLM_API_KEY` = ключ OpenAI, `LLM_MODEL` задаёт модель (например `gpt-5-nano-2025-08-07`), `LLM_REASONING_EFFORT` управляет режимом рассуждений (`none|low|medium|high`), `LLM_SYSTEM_PROMPT_PATH` указывает файл системного промпта, `LLM_USER_PROMPT_PATH` — файл пользовательского промпта.
     • `BATCH_SIZE`, `MAX_RPS`, `MAX_RPM`.
     • `CONFIG_PATH`, `MAPPING_PATH` — позволяют переопределять путь к yaml-конфига и mapping-файлу.
   - `config/config.yaml`: используется по умолчанию (можно подменить через `CONFIG_PATH`). Внутри храним структурированный словарь `runtime`, `google_auth`, `source_sheet`, `sink_sheet`, `llm`, `mapping`, `brand_registry`. Значения допускают плейсхолдеры `${ENV_NAME}` — загрузчик заменит их фактическими значениями из окружения.
   - `config/mapping.yaml`: основной mapping, который расписывает правила вида {name, source, (json_path|source_column|const_value), target_column, transform[], write_if_empty}. В текущем эталоне перечислены ключевые поля Bitrix (IE_NAME, IE_NAME_MINOR, IP_PROP**** и т.д.) и обязательно IE_XML_ID/image_path.
   - Доступ к JSON сервисного аккаунта обеспечивается через хостовую папку `./secrets`, смонтированную в контейнер `processor` (read-only) по умолчанию; внутри ожидается файл `google-credentials.json`, путь указан в `.env`.

4. Технологический стек
   - Язык: Python 3.12 (см. Dockerfile). Все зависимости закрепим в `requirements.txt` (pydantic, pydantic-settings, httpx, gspread, google-auth, typer, structlog, tenacity, PyYAML, pytest и т.д.).
   - Клиент Google Sheets: `gspread` + `google-auth` (сервисный аккаунт). Планируется единый клиент, от которого наследуются source/sink адаптеры.
   - HTTP/LLM: `httpx` (sync) с ретраями (tenacity) и валидациями через `pydantic`.
   - CLI: `typer` (команды run, dry-run, validate-config).
   - Тесты: `pytest`, `pytest-mock`, `respx`/`responses` для моков HTTP, фикстуры mapping/config в `tests/fixtures`.
   - Контейнеризация: Docker Desktop, одиночный сервис `processor` в `docker-compose.yml`; запуск `docker compose up processor` или `docker run --env-file .env raw-to-finished-data`.

5. Логирование и мониторинг
   - Все модули пишут структурированные логи (JSON или key=value) в stdout, Docker Desktop собирает их.
   - Ключевые события: старт батча, количество успешных/ошибочных строк, ошибки LLM, ошибки записи в приёмник.
   - Для отладки сохраняем llm_raw (опционально) либо в отдельную колонку источника, либо в metadata под ключом `llm_raw`.

6. Обработка ошибок и идемпотентность
   - Если `product_content` пустой, строка сразу помечается статусом error с note.
   - При сетевых ошибках работаем с экспоненциальным backoff и лимитом попыток; при превышении лимита строка получает статус error.
   - Режим upsert_by_xml_id обеспечивает идемпотентность за счёт уникального product_id_hash (маппится на IE_XML_ID). Повторный запуск не перезаписывает поля, которых нет в патче.

7. Тестирование
   - `tests/unit` — конфиг-лоадеры, mapping engine, трансформации, генерация патчей.
   - `tests/integration` — мок Google Sheets/LLM для проверки полных сценариев (append и upsert).
   - Для тестов используем локальные фикстуры mapping/config и временные JSON-файлы; запускать через `docker run --rm <image> pytest`.

8. Связь с планом
   - Соответствие этапам в docs/plan.md: пункты 2–7 реализуют описанные здесь компоненты. Любые изменения архитектуры отражаем и здесь, и в планах, прежде чем помечать этап «выполнено».
