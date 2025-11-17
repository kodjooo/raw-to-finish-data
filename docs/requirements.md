ТЕХНИЧЕСКОЕ ЗАДАНИЕ
Скрипт ИИ-агента для структурирования описаний товаров из Google Sheets и записи результата в битриксовую таблицу-приёмник

1) Цель

Нужно автоматизировать обработку сырых описаний товаров из Google Таблицы-источника.
Скрипт берёт строки со статусом «Не обработано», отправляет в ИИ-агент по API:

- текст описания товара product_content;
- категорию товара category (контекст для ИИ).

В ответ ИИ возвращает структурированный JSON с полями товара. Скрипт:

- сопоставляет поля JSON с колонками таблицы-приёмника (битриксовый шаблон) через конфиг-mapping;
- заполняет по конкретному товару только те поля приёмника, для которых:
  • есть правило в mapping
  И
  • у агента реально пришло непустое значение;
- прокидывает image_path из источника в приёмник без изменений;
- после успешной записи в приёмник меняет статус строки в источнике на «Обработано», при ошибке — «Ошибка» и пишет текст ошибки в note.


2) Структура листа Источника (Google Sheet A)

Используем существующие поля:

- source_site — домен/источник товара.
- category — категория товара (обязательно отправляем в GPT).
- category_url — URL страницы категории.
- product_url — URL карточки товара.
- product_content — неструктурированное описание товара (главный текст для GPT).
- discovered_at — время, когда товар найден.
- run_id — идентификатор запуска парсера.
- status — статус обработки товара:
  • «Не обработано» (или другое значение, задаётся в конфиге),
  • «Обработано»,
  • «Ошибка».
- note — комментарий/ошибка обработки.
- product_id_hash — хэш/уникальный идентификатор товара (ключ для связи с приёмником и идемпотентности).
- page_num — номер страницы в категории.
- metadata — произвольное служебное поле (JSON/текст, по необходимости).
- image_path — путь к картинке (локальный путь или URL), должен уйти в приёмник как есть.

Опционально можно добавить:

- processed_at — дата/время успешной обработки GPT;
- llm_raw — сырой ответ ИИ для отладки.

Если этих полей нет, скрипт может хранить служебные данные внутри metadata.


3) Структура листа Приёмника (Google Sheet B, битриксовый формат)

Приёмник — таблица с колонками под импорт в 1С-Битрикс. Актуальный список (в порядке столбцов) выглядит так:

ID элемента {IE_ID}
Внешний код {IE_XML_ID}
Ссылка у конкурента {IE_LINK_RIVAL} — заполняем из `product_url`
Наименование у конкурента (en) {IE_NAME_RIVAL_EN} — заполняем из колонки источника `name (en)`
Наименование у конкурента (ru) {IE_NAME_RIVAL_RU} — заполняем из колонки источника `name (ru)`
Наименование элемента {IE_NAME}
Артикул [CML2_ARTICLE] {IP_PROP1001}
Детальная картинка (путь) {IE_DETAIL_PICTURE}
Картинки галереи [MORE_PHOTO] {IP_PROP1006} — оставляем пустым
Детальное описание {IE_DETAIL_TEXT}
Тип детального описания {IE_DETAIL_TEXT_TYPE}
Путь из названий разделов {IE_SECTION_PATH}
Название раздела {ISECT_NAME} — заполняем значением `category` (fallback к section_path)
Символьный код {ISECT_CODE} — заполняем значением `category_slug`
Внешний код {ISECT_XML_ID} — не заполняем
Старая цена {ICAT_PRICE_WITHOUT_DISCOUNT} — заполняем из колонки источника `price (without discount)`
Цена "Цена" {ICAT_PRICE5_PRICE} — заполняем из колонки источника `price (with discount)`
Цена "Цена Сайт Белгород" {ICAT_PRICE6_PRICE}
Цена "Розничная цена Краснодар" {ICAT_PRICE4_PRICE}
Цена "Розничная цена (Орел)" {ICAT_PRICE3_PRICE}
Вес (грамм) {ICAT_WEIGHT}
Штрихкод {ICAT_BARCODE}
Цвет [TSVET] {IP_PROP1059}
Автор [AVTOR] {IP_PROP1009}
Виноградники [VINOGRADNIKI] {IP_PROP1060}
Содержание сахара [SODERZHANIE_SAKHARA] {IP_PROP1045}
Сортовой состав [SORTOVOY_SOSTAV] {IP_PROP1072}
Страна [STRANA] {IP_PROP1051}
Регион [REGION] {IP_PROP1042}
Аппелласьон [APPELLASON] {IP_PROP1010}
Выдержка в ёмкости [VYDERZHKA_V_YEMKOSTI] {IP_PROP1062}
Бренд [BREND] {IP_PROP1012}
Глубина цвета [GLUBINA_TSVETA] {IP_PROP1063}
Объем [OBEM] {IP_PROP1035}
Крепость [KREPOST] {IP_PROP1120}
Виноград [VINOGRAD] {IP_PROP1013}
Винтаж [VINTAZH] {IP_PROP1061}
Дата розлива [DATA_ROZLIVA] {IP_PROP1064}
Производитель [CML2_MANUFACTURER] {IP_PROP1008}
Населенный пункт [NASELENNYY_PUNKT] {IP_PROP1068}
Вкус Бакалея [VKUS_BAKALEYA] {IP_PROP1015}
Классификация [KLASSIFIKATSIYA] {IP_PROP1029}
Год урожая [GOD_UROZHAYA] {IP_PROP1022}
Награды [NAGRADY] {IP_PROP1067}
Возрастное ограничение: [VOZRASTNOE_OGRANICHENIE] {IP_PROP1018}
Способ выдержки [SPOSOB_VYDERZHKI] {IP_PROP1073}
Год издания: [GOD_IZDANIYA] {IP_PROP1021}
Стиль вина [STIL_VINA] {IP_PROP1074}
Издательский бренд: [IZDATELSKIY_BREND] {IP_PROP1024}
Танинность [TANINNOST] {IP_PROP1075}
Импортер [IMPORTER] {IP_PROP1025}
КБЖУ [KBZHU] {IP_PROP1028}
Торговая марка [TORGOVAYA_MARKA] {IP_PROP1080}
Количество страниц [KOLICHESTVO_STRANITS] {IP_PROP1030}
Начинка/вкус [NACHINKA_VKUS] {IP_PROP1034}
Срок выдержки [SROK_VYDERZHKI_DLYA_KREPKOGO_ALKOGOLYA] {IP_PROP1049}
Выдержка [VYDERZHKA] {IP_PROP1019}
Оттенок [OTTENOK_1] {IP_PROP1070}
Тип виски [TIP_VISKI] {IP_PROP1054}
Кислотность [KISLOTNOST] {IP_PROP1066}
Аромат [AROMAT] {IP_PROP1011}
Вкус [VKUS] {IP_PROP1014}
Состав [SOSTAV] {IP_PROP1047}
Тело / Насыщенность [TELO_NASYSHCHENNOST] {IP_PROP1076}
срок годности_сыр [SROK_GODNOSTI_SYR] {IP_PROP1050}
Температура подачи [TEMPERATURA_PODACHI] {IP_PROP1077}
Тара [TARA] {IP_PROP1052}
Технологические особенности [TEKHNOLOGICHESKIE_OSOBENNOSTI] {IP_PROP1079}
Терруар [TERRUAR] {IP_PROP1078}
Сорт (Моносорт/Бленд) [SORT_MONOSORT_BLEND] {IP_PROP1046}
Потенциал хранения [POTENTSIAL_KHRANENIYA] {IP_PROP1071}
Упаковка [UPAKOVKA] {IP_PROP1056}

Важный момент:
Скрипт не обязан заполнять все эти поля. Он должен заполнять только те из них, которые указаны в mapping и для которых у агента есть данные по данному товару. Остальные столбцы либо остаются пустыми (для новых строк), либо не трогаются (для обновления существующих строк).


4) Формат ответа ИИ-агента

ИИ возвращает строго JSON-объект. Структура задаётся промптом, но пример для алкоголя может быть таким:

Минимальный набор ключей, которые должны присутствовать в ответе (допускаются дополнительные поля, но перечисленные нельзя опускать — при отсутствии значения ставим null, однако формат сохраняем):
- `name`, `brand`, `country`, `region`.
- `grape_varieties` — массив строк (каждый сорт отдельным элементом).
- `sugar`, `volume`, `abv`, `vintage`, `aroma`, `taste`, `classification`.
- `description_html` — HTML с параграфами `<p>...</p>`.
- `section_path` — строка вида `Категория/Подкатегория` без пробелов вокруг `/`. Если агент не прислал `section_path`, используем `category_path` как fallback (строка хранится целиком, без разбиения по другим колонкам).
- `section_name` — последняя часть `section_path` (в текущей реализации приёмник больше не заполняется этим полем).
- `section_code` — slug для `section_name` (в текущей реализации не заполняем, но агент всё равно может присылать значение).
- `prices` → `retail` — число (или строка) с точкой в качестве разделителя дробной части.
Для `volume` используем литры в формате строки с точкой (например `0.75`), для `abv` — только цифры и точку без знака `%`, `vintage` — четыре цифры.
Все текстовые значения обязаны быть валидными для JSON: не оставляем неэкранированные двойные кавычки внутри строк (либо заменяем их на «ёлочки», либо экранируем символом `\"`), переносы строк задаём через `\n`.
Поля `category`, `category_path`, `category_slug` в JSON не используем; вся информация о разделе должна быть выражена только через `section_*`.

Дополнительно агент может (и желательно, чтобы делал) присылать вспомогательные ключи:
- `description` — fallback-текст, если по каким-то причинам не удалось отрендерить `description_html`. Мы всё равно заполним колонку IE_DETAIL_TEXT, но при наличии `description_html` он имеет приоритет.
- `sugar_content`, `volume_l`, `alcohol_percent`, `vintage_year` — дубликаты основных свойств. Пайплайн автоматически заменяет запятую на точку для `volume_l` и убирает символ `%` у `alcohol_percent`, чтобы значения корректно ложились в Bitrix.
- `manufacturer`, `color`, `temperature_serving` — кладём в соответствующие свойства (`IP_PROP1008`, `IP_PROP1059`, `IP_PROP1077`).
- `category_path` — может дублировать `section_path`, но мы не разбиваем строку «Вино / Красное» по отдельным ячейкам (используем только колонку `Путь из названий разделов {IE_SECTION_PATH}`); `category` маппится в `ISECT_NAME`, `category_slug` — в `ISECT_CODE`.
- `grape_varieties_string` или случаи, когда `grape_varieties` приходит строкой — пайплайн автоматически разобьёт значение по запятым и превратит его в массив перед применением mapping.
- `volume`/`volume_l` и `abv`/`alcohol_percent` при записи в Bitrix всегда конвертируются в строки с запятой в качестве десятичного разделителя; для крепости (`abv`) дополнительно добавляем знак `%` (пример: `0,75` и `13,5%`), независимо от того, в каком формате их вернул LLM.
- Дополнительные свойства, которые агент может отправить в JSON и которые мы сохраняем напрямую в Bitrix: `appellation` (→ IP_PROP1010), `aging` (→ IP_PROP1019), `production_method` (→ IP_PROP1073), `acidity` (→ IP_PROP1066), `body` (→ IP_PROP1076), `technical_features` (→ IP_PROP1079), `terroir` (→ IP_PROP1078). Поле `serving_temperature` — синоним `temperature_serving`.
- Колонки источника (`product_url`, `name (en)`, `name (ru)`, `price (without discount)`, `price (with discount)`) сразу перекладываются в соответствующие поля приёмника (IE_LINK_RIVAL, IE_NAME_RIVAL_EN, IE_NAME_RIVAL_RU, ICAT_PRICE_WITHOUT_DISCOUNT, ICAT_PRICE5_PRICE) после нормализации значений (обрезаем пробелы, удаляем текст вроде `руб`, оставляем только цифры/знаки, приводим цены к числу).
  Цены дополнительно форматируются в строку вида `2994.00` (две десятичные, разделитель — точка).

{
  "name": "Шампанское Brut Rose",
  "brand": "Some Brand",
  "country": "France",
  "region": "Champagne",
  "grape_varieties": ["Pinot Noir", "Chardonnay"],
  "sugar": "Brut",
  "volume": "0.75",
  "abv": "12.5",
  "vintage": "2018",
  "aroma": "Ягоды, тосты",
  "taste": "Свежий, ягодный, с хорошей кислотностью",
  "color": "Розовый",
  "classification": "AOC",
  "description_html": "<p>Подробное описание…</p>",
  "section_path": "Вино/Игристое/Франция/Шампань",
  "section_name": "Шампанское"
}

Точный контракт (какие поля могут прийти) фиксируется в отдельном описании схемы, но скрипт должен быть готов к следующему:

- если поля нет в JSON — он считается «не пришёл от агента» и не должен перезаписывать соответствующую колонку приёмника;
- если поле есть, но пустое/null, по умолчанию скрипт тоже не должен им затирать уже существующее значение (правило «обновляем только непустыми значениями»).


5) Карта соответствий (mapping) и логика «заполняем только то, что пришло»

Mapping хранится в отдельном файле (например, mapping.json или mapping.yaml).

Для каждого поля приёмника можно задать правило:

- откуда брать значение:
  • source: "json" — из ответа агента;
  • source: "source_row" — из строки источника (например, image_path → IE_DETAIL_PICTURE);
  • source: "const" — фиксированное значение (например, IE_DETAIL_TEXT_TYPE = "text").
- путь к полю:
  • для json — json_path в формате dot-notation или JSONPath;
  • для source_row — название колонки источника;
- target_column — название колонки приёмника (из списка выше);
- опционально transform — список преобразований (strip, number и т.п.);
- опционально required — только для контроля схемы;
- флаг поведения при пустом значении: write_if_empty: true|false.

Главный принцип, который обязательно заложить в реализацию:

по товару заполняются только те поля приёмника, для которых одновременно:
- есть правило в mapping;
- удалось получить не пустое значение (после трансформаций) из json или строки источника;
- для source: "const" значение считается «пришедшим» по определению.

Если в JSON нет, например, grape_varieties, то колонка [VINOGRAD] {IP_PROP1013} не трогается вообще.

Пример mapping (фрагмент):

[
  { "source": "source_row", "source_column": "product_id_hash", "target_column": "IE_XML_ID" },
  { "source": "source_row", "source_column": "image_path", "target_column": "IE_DETAIL_PICTURE" },

  { "source": "json", "json_path": "$.name", "target_column": "IE_NAME", "transform": ["strip"] },
  { "source": "json", "json_path": "$.brand", "target_column": "IP_PROP1012" },                 // Бренд
  { "source": "json", "json_path": "$.country", "target_column": "IP_PROP1051" },               // Страна
  { "source": "json", "json_path": "$.region", "target_column": "IP_PROP1042" },                // Регион
  { "source": "json", "json_path": "$.grape_varieties", "target_column": "IP_PROP1013", "transform": ["join(', ')"] }, // Виноград
  { "source": "json", "json_path": "$.sugar", "target_column": "IP_PROP1045" },                 // Содержание сахара
  { "source": "json", "json_path": "$.volume", "target_column": "IP_PROP1035" },                // Объем
  { "source": "json", "json_path": "$.abv", "target_column": "IP_PROP1120" },                   // Крепость
  { "source": "json", "json_path": "$.vintage", "target_column": "IP_PROP1061" },               // Винтаж
  { "source": "json", "json_path": "$.aroma", "target_column": "IP_PROP1011" },                 // Аромат
  { "source": "json", "json_path": "$.taste", "target_column": "IP_PROP1014" },                 // Вкус
  { "source": "json", "json_path": "$.classification", "target_column": "IP_PROP1029" },        // Классификация
  { "source": "json", "json_path": "$.description_html", "target_column": "IE_DETAIL_TEXT" },
  { "source": "const", "const_value": "text", "target_column": "IE_DETAIL_TEXT_TYPE" },
  { "source": "json", "json_path": "$.section_path", "target_column": "IE_SECTION_PATH" },
  { "source": "json", "json_path": "$.section_name", "target_column": "ISECT_NAME" }
]

Логика обработки mapping:

- Скрипт проходит по mapping.
- Для каждого правила достаёт значение из указанного источника (json, source_row или const).
- Применяет transform (если заданы).
- Если значение пустое (None, пустая строка, пустой массив) и write_if_empty не установлен или false — этот target_column ПРОПУСКАЕТСЯ для данного товара.
- Только колонки, которые получили непустые значения, попадают в патч на запись в приёмник.


6) Передача category и image_path

В запрос к GPT скрипт обязательно добавляет:

- content = product_content;
- category из поля category источника.

Дополнительно можно (по желанию) передавать source_site, product_url и т.п., но это опционально.

image_path в GPT не отправляется. Он берётся только из источника и используется при формировании строки приёмника:

- через правило mapping: source_row.image_path → IE_DETAIL_PICTURE (IP_PROP1006 не используем и оставляем пустым).
- значение не меняется: никаких скачиваний файлов, перезаливок и т.д.
- показатели `stocks.store_*` из ответа ИИ игнорируем — все колонки количества на складах оставляем пустыми.


7) Конфигурация скрипта

Во внешнем config.yaml задаются:

- параметры доступа к Google Sheets (ID таблиц, имена листов);
- названия колонок в источнике:
  • status_column, status_new, status_done, status_error;
  • content_column = "product_content";
  • category_column = "category";
  • image_path_column = "image_path";
  • id_column = "product_id_hash";
  • note_column = "note";
- ID и лист приёмника (битриксовый шаблон);
- путь к mapping-файлу;
- параметры ИИ-агента (URL, модель, ключ, таймаут, retries);
- размер батча за один запуск, лимиты RPS/RPM;
- режим записи в приёмник:
  • sink_mode: "append" — всегда добавляем новую строку;
  • sink_mode: "upsert_by_xml_id" — ищем по IE_XML_ID = product_id_hash и обновляем только те колонки, для которых пришло значение.

При upsert обновление происходит «патчем» по колонкам, а не перезаписью всей строки, чтобы не трогать цены/остатки и другие поля, не связанные с GPT.


8) Алгоритм работы

Скрипт:

1. Читает из источника строки, где status = status_new.
2. Для каждой строки проверяет наличие product_content.
   - Если поле пустое:
     • status = status_error,
     • note = "Пустой product_content",
     • переход к следующей строке.
3. Формирует payload для ИИ:
   - включает product_content, category, при необходимости source_site и др. как контекст.
4. Дёргает ИИ с ретраями и таймаутами.
5. Парсит ответ как JSON, валидирует по схеме.
6. На основе mapping и данных:
   - JSON-ответа;
   - строки источника;
   - констант
   формирует «патч» для строки приёмника: словарь target_column → value.
   В патч попадают только те пары, где:
   - есть правило mapping;
   - значение не пустое (или source = const).
7. Записывает патч в приёмник:
   - при append — создаёт новую строку и заполняет только эти колонки, остальные остаются пустыми;
   - при upsert — находит строку по ключу (например, IE_XML_ID = product_id_hash) и обновляет только эти колонки, остальные не трогает.
8. При успехе:
   - status = status_done,
   - note очищается или заполняется "OK",
   - при наличии поля processed_at — туда пишется текущий timestamp.
9. При любой ошибке:
   - status = status_error,
   - note получает краткое описание ошибки.


9) Псевдокод обработки одной строки

row = source_row
if not row.product_content:
    mark_error(row, "Пустой product_content")
    continue

llm_payload = {
    "content": row.product_content,
    "category": row.category,
    ...
}

raw_response = call_llm_with_retries(llm_payload)
json_obj = parse_and_validate(raw_response)

patch = {}
for rule in mapping:
    value = get_value(rule, json_obj, row)      # json / source_row / const
    value = apply_transforms(rule, value)
    if is_empty(value) and not rule.write_if_empty:
        continue
    patch[rule.target_column] = value

if not patch:
    mark_error(row, "Нет данных для записи от агента")
    continue

write_patch_to_sink(
    patch,
    key=row.product_id_hash,
    mode=config.sink_mode  # append | upsert_by_xml_id
)

mark_done(row)


10) Критерии приёмки

- Скрипт берёт строки со статусом «Не обработано», отправляет в GPT product_content и category.
- В приёмник попадают только те колонки, которые:
  • есть в mapping;
  • реально получили непустые значения от агента или из источника (image_path, product_id_hash и т.п.).
- Остальные колонки приёмника не затираются и остаются как есть.
- image_path корректно прокидывается в выбранную колонку (как минимум IE_DETAIL_PICTURE) без изменения значения.
- После успешной записи статус источника меняется на «Обработано», при ошибках — «Ошибка» с понятным текстом в note.
