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
            "price (with discount)": "987,65",
            "price (without discount)": "1 111,50",
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
                transform=["comma_to_dot"],
            ),
            MappingRule(
                name="abv-percent",
                source=MappingSource.JSON,
                json_path="$.alcohol_percent",
                target_column="ABV",
                transform=["strip_percent", "float"],
            ),
            MappingRule(
                name="section-path",
                source=MappingSource.JSON,
                json_path="$.section_path",
                target_column="IE_SECTION_PATH",
                transform=["normalize_slash_path"],
            ),
        ]
    )
    engine = MappingEngine(table)
    llm_data = {
        "name": "  Test Name  ",
        "grape_varieties": ["Cabernet", "Merlot"],
        "volume_l": "0,75",
        "alcohol_percent": "13.5%",
        "section_path": "Вино / Красное",
    }

    patch = engine.build_patch(llm_data=llm_data, source_row=_source_row())

    assert patch["IE_XML_ID"] == "hash123"
    assert patch["IE_NAME"] == "Test Name"
    assert patch["IP_PROP1013"] == "Cabernet, Merlot"
    assert patch["IE_DETAIL_TEXT_TYPE"] == "text"
    assert patch["ICAT_PRICE_WITHOUT_DISCOUNT"] == 1111.50
    assert patch["ICAT_PRICE5_PRICE"] == 987.65
    assert patch["IE_NAME_RIVAL_EN"] == "Rival EN"
    assert patch["VOLUME"] == "0,75"
    assert patch["ABV"] == "13,5%"
    assert patch["IE_SECTION_PATH"] == "Вино/Красное"


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
