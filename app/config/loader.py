from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from app.config.models import AppConfig, MappingTable

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _substitute_env(value: str, env: Dict[str, str]) -> str:
    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name not in env:
            raise KeyError(f"Не задано переменной окружения {var_name}")
        return env[var_name]

    return _ENV_PATTERN.sub(_replace, value)


def _walk_and_replace(data: Any, env: Dict[str, str]) -> Any:
    if isinstance(data, dict):
        return {k: _walk_and_replace(v, env) for k, v in data.items()}
    if isinstance(data, list):
        return [_walk_and_replace(item, env) for item in data]
    if isinstance(data, str):
        if "${" in data:
            substituted = _substitute_env(data, env)
            if not substituted.strip():
                return None
            return substituted
        if not data.strip():
            return None
        return data
    return data


def load_app_config(path: str | Path, *, env: Dict[str, str] | None = None) -> AppConfig:
    env = env or os.environ
    raw_data = _read_yaml(path)
    substituted = _walk_and_replace(raw_data, env)
    return AppConfig(**substituted)


def load_mapping(path: str | Path) -> MappingTable:
    raw_data = _read_yaml(path)
    if raw_data is None:
        raw_data = []
    if isinstance(raw_data, dict):
        raw_data = raw_data.get("rules", [])
    if not isinstance(raw_data, Iterable):
        raise ValueError("mapping.yaml должен содержать массив правил")
    return MappingTable.from_raw(list(raw_data))


def _read_yaml(path: str | Path) -> Any:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Не найден конфиг {resolved}")
    with resolved.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)
