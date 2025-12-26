from app.config.models import MappingRule, MappingSource, MappingTable
from app.core.mapping_engine import MappingEngine
from app.orchestrator.models import SourceRow


def _source_row() -> SourceRow:
    return SourceRow(
        row_index=2,
        product_id="hash123",
        product_content="описание",
        category="wine",
        image_path="/img.jpg",
        raw_values={
            "product_id_hash": "hash123",
            "image_path": "/img.jpg",
            "status": "Не обработано",
            "name (en)": "  Rival EN ",
            "name (ru)": "Риваль RU ",
            "price (with discount)": "987,65 руб",
            "price (without discount)": "1\xa0111,50 руб",
        },
    )


def test_build_patch_applies_transforms_and_rules() -> None:
    table = MappingTable(
        rules=[
            MappingRule(
                name="xml-id",
                source=MappingSource.SOURCE_ROW,
                source_column="product_id_hash",
                target_column="IE_XML_ID",
            ),
            MappingRule(
                name="name",
                source=MappingSource.JSON,
                json_path="$.name",
                target_column="IE_NAME",
                transform=["strip"],
            ),
            MappingRule(
                name="grapes",
                source=MappingSource.JSON,
                json_path="$.grape_varieties",
                target_column="IP_PROP1013",
                transform=["join(', ')"]
            ),
            MappingRule(
                name="const-type",
                source=MappingSource.CONST,
                const_value="text",
                target_column="IE_DETAIL_TEXT_TYPE",
            ),
            MappingRule(
                name="price-old",
                source=MappingSource.SOURCE_ROW,
                source_column="price (without discount)",
                target_column="ICAT_PRICE_WITHOUT_DISCOUNT",
                transform=["comma_to_dot", "float"],
            ),
            MappingRule(
                name="price-current",
                source=MappingSource.SOURCE_ROW,
                source_column="price (with discount)",
                target_column="ICAT_PRICE5_PRICE",
                transform=["comma_to_dot", "float"],
            ),
            MappingRule(
                name="rival-en",
                source=MappingSource.SOURCE_ROW,
                source_column="name (en)",
                target_column="IE_NAME_RIVAL_EN",
                transform=["strip"],
            ),
            MappingRule(
                name="volume-liters",
                source=MappingSource.JSON,
                json_path="$.volume_l",
                target_column="VOLUME",
                transform=["comma_to_dot", "to_string", "append_liters_suffix"],
            ),
            MappingRule(
                name="abv-percent",
                source=MappingSource.JSON,
                json_path="$.alcohol_percent",
                target_column="ABV",
                transform=["strip_percent", "comma_to_dot", "to_string", "append_percent"],
            ),
            MappingRule(
                name="vivino-score",
                source=MappingSource.JSON,
                json_path="$.vivino_score",
                target_column="VIVINO_SCORE",
                transform=["to_string", "strip"],
            ),
            MappingRule(
                name="section-path",
                source=MappingSource.JSON,
                json_path="$.section_path",
                target_column="IE_SECTION_PATH",
                transform=["normalize_slash_path"],
            ),
            MappingRule(
                name="section-path-fallback",
                source=MappingSource.JSON,
                json_path="$.category_path",
                target_column="IE_SECTION_PATH",
                transform=["normalize_slash_path"],
            ),
            MappingRule(
                name="section-name-category",
                source=MappingSource.JSON,
                json_path="$.category",
                target_column="ISECT_NAME",
                transform=["strip"],
            ),
            MappingRule(
                name="section-code-category-slug",
                source=MappingSource.JSON,
                json_path="$.category_slug",
                target_column="ISECT_CODE",
                transform=["strip"],
            ),
            MappingRule(
                name="producer",
                source=MappingSource.JSON,
                json_path="$.producer",
                target_column="CML2_MANUFACTURER",
                transform=["strip"],
            ),
            MappingRule(
                name="classifier",
                source=MappingSource.JSON,
                json_path="$.classifier",
                target_column="IP_PROP1029",
                transform=["strip"],
            ),
        ]
    )
    engine = MappingEngine(table)
    llm_data = {
        "name": "  Test Name  ",
        "name_minor": "  Test Minor ",
        "grape_varieties": ["Cabernet", "Merlot"],
        "volume_l": "0,75",
        "alcohol_percent": "13.5%",
        "section_path": "Вино / Красное",
        "category_path": "Вино / Десертное",
        "category": "  Красное ",
        "category_slug": "krasnoe",
        "vivino_score": " 4.3 ",
        "producer": "  Producer Inc ",
        "classifier": "DOC",
    }

    patch = engine.build_patch(llm_data=llm_data, source_row=_source_row())

    assert patch["IE_XML_ID"] == "hash123"
    assert patch["IE_NAME"] == "Test Name"
    assert patch["IE_NAME_MINOR"] == "Test Minor"
    assert patch["IP_PROP1013"] == "Cabernet, Merlot"
    assert patch["IE_DETAIL_TEXT_TYPE"] == "text"
    assert patch["ICAT_PRICE_WITHOUT_DISCOUNT"] == 1111.5
    assert patch["ICAT_PRICE5_PRICE"] == 987.65
    assert patch["IE_NAME_RIVAL_EN"] == "Rival EN"
    assert patch["VOLUME"] == "0.75 л"
    assert patch["ABV"] == "13.5 %"
    assert patch["IE_SECTION_PATH"] == "Вино/Красное"
    assert patch["ISECT_NAME"] == "Красное"
    assert patch["ISECT_CODE"] == "krasnoe"
    assert patch["VIVINO_SCORE"] == "4.3"
    assert patch["CML2_MANUFACTURER"] == "Producer Inc"
    assert patch["IP_PROP1029"] == "DOC"


def test_section_path_fallback_used_when_primary_missing() -> None:
    table = MappingTable(
        rules=[
            MappingRule(
                name="section-path",
                source=MappingSource.JSON,
                json_path="$.section_path",
                target_column="IE_SECTION_PATH",
                transform=["normalize_slash_path"],
            ),
            MappingRule(
                name="section-path-fallback",
                source=MappingSource.JSON,
                json_path="$.category_path",
                target_column="IE_SECTION_PATH",
                transform=["normalize_slash_path"],
            ),
        ]
    )
    engine = MappingEngine(table)
    llm_data = {"category_path": "Вино / Десертное"}

    patch = engine.build_patch(llm_data=llm_data, source_row=_source_row())

    assert patch["IE_SECTION_PATH"] == "Вино/Десертное"


def test_empty_values_are_skipped_without_flag() -> None:
    table = MappingTable(
        rules=[
            MappingRule(
                name="empty",
                source=MappingSource.JSON,
                json_path="$.missing",
                target_column="IE_NAME",
            ),
            MappingRule(
                name="write-empty",
                source=MappingSource.JSON,
                json_path="$.note",
                target_column="NOTE",
                write_if_empty=True,
            ),
        ]
    )
    engine = MappingEngine(table)
    llm_data = {"note": ""}

    patch = engine.build_patch(llm_data=llm_data, source_row=_source_row())

    assert "IE_NAME" not in patch
    assert patch["NOTE"] == ""
