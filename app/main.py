"""Точка входа CLI сервиса raw-to-finished-data."""

from app.cli import app


def main() -> None:
    """Запуск Typer CLI."""
    app()


if __name__ == "__main__":
    main()
