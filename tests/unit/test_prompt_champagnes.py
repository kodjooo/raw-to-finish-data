from pathlib import Path


def test_champagnes_prompt_example_is_sparkling() -> None:
    content = Path("config/system_prompt_champagnes.txt").read_text(encoding="utf-8")
    assert "Категория: игристое вино" in content
    assert "Категория: вино " not in content
