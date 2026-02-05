from pathlib import Path


def test_spirit_prompt_has_no_wine_examples() -> None:
    content = Path("config/system_prompt_spirit.txt").read_text(encoding="utf-8")
    assert "Категория: вино" not in content
    assert "wine_classifiers.json" not in content


def test_spirit_prompt_example_includes_requested_fields() -> None:
    content = Path("config/system_prompt_spirit.txt").read_text(encoding="utf-8")
    assert "“aging”" in content
    assert "“aging_barrel”" in content
    assert "“color_shade”" in content
    assert "“whisky_type”" in content


def test_spirit_prompt_classifier_rules_for_spirits() -> None:
    content = Path("config/system_prompt_spirit.txt").read_text(encoding="utf-8")
    assert "Коньяк/Арманьяк/Бренди/Кальвадос" in content
    assert "классификатор остаётся отдельным полем JSON" in content
    assert "Арманьяк: VSOP, VS, XO, Hors d'Age" in content
    assert "Бренди: VSOP, VS, XO, AC, Hors d'Age, Vintage, Napoleon" in content
    assert "Кальвадос: VSOP, VS, XO, Hors d'Age" in content
    assert "Коньяк: используй найденный" in content
    assert "ВСОП → VSOP" in content
    assert "ВС → VS" in content
    assert "ХО → XO" in content
    assert "ХОР Д'АЖ → Hors d'Age" in content
    assert "НАПОЛЕОН → Napoleon" in content
    assert "ВИНТАЖ → Vintage" in content
    assert "АС → AC" in content
    assert "НИКАКОГО перевода/латинизации не делать" in content
