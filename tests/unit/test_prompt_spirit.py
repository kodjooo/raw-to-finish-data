from pathlib import Path


def test_spirit_prompt_has_no_wine_examples() -> None:
    content = Path("config/system_prompt_spirit.txt").read_text(encoding="utf-8")
    assert "Категория: вино" not in content
    assert "wine_classifiers.json" not in content
