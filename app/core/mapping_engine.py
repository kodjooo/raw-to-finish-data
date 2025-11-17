from __future__ import annotations

import re
from typing import Any, Dict, Iterable

from app.config.models import MappingRule, MappingSource, MappingTable
from app.orchestrator.models import SourceRow

_JSON_PATH_RE = re.compile(r"(?P<key>[^.\[]+)(?:\[(?P<index>\d+)\])?")


class MappingEngine:
    def __init__(self, table: MappingTable) -> None:
        self._rules = table.rules

    def build_patch(self, *, llm_data: Dict[str, Any], source_row: SourceRow) -> Dict[str, Any]:
        patch: Dict[str, Any] = {}
        for rule in self._rules:
            value = self._extract_value(rule, llm_data, source_row)
            if value is None and rule.source is not MappingSource.CONST:
                continue
            value = self._apply_transforms(value, rule.transform)
            if self._is_empty(value) and not (rule.write_if_empty or rule.source is MappingSource.CONST):
                continue
            existing = patch.get(rule.target_column)
            if existing is not None and not self._is_empty(existing) and not rule.write_if_empty:
                # уже записали непустое значение — не перетираем fallback-правилами
                continue
            patch[rule.target_column] = value
        return patch

    def _extract_value(
        self, rule: MappingRule, llm_data: Dict[str, Any], source_row: SourceRow
    ) -> Any:
        if rule.source is MappingSource.JSON:
            return self._extract_from_json(llm_data, rule.json_path or "")
        if rule.source is MappingSource.SOURCE_ROW:
            return source_row.raw_values.get(rule.source_column or "")
        if rule.source is MappingSource.CONST:
            return rule.const_value
        raise ValueError(f"Неизвестный источник данных {rule.source}")

    def _extract_from_json(self, data: Dict[str, Any], path: str) -> Any:
        if not path.startswith("$."):
            raise ValueError(f"json_path должен начинаться с $. ({path})")
        current: Any = data
        for token in path[2:].split('.'):
            if token == "":
                continue
            match = _JSON_PATH_RE.fullmatch(token)
            if not match:
                return None
            key = match.group("key")
            index = match.group("index")
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return None
            if index is not None:
                if not isinstance(current, list):
                    return None
                idx = int(index)
                if idx >= len(current):
                    return None
                current = current[idx]
            if current is None:
                return None
        return current

    def _apply_transforms(self, value: Any, transforms: Iterable[str]) -> Any:
        result = value
        for transform in transforms or []:
            if transform == "strip":
                result = result.strip() if isinstance(result, str) else result
            elif transform == "lower":
                result = result.lower() if isinstance(result, str) else result
            elif transform == "upper":
                result = result.upper() if isinstance(result, str) else result
            elif transform.startswith("join(") and transform.endswith(")"):
                if isinstance(result, (list, tuple)):
                    separator = transform[5:-1]
                    if separator.startswith(("'", '"')) and separator.endswith(("'", '"')):
                        separator = separator[1:-1]
                    result = separator.join(str(item) for item in result if item)
            elif transform in {"number", "float"}:
                try:
                    result = float(result)
                except (TypeError, ValueError):
                    return None
            elif transform == "int":
                try:
                    result = int(float(result))
                except (TypeError, ValueError):
                    return None
            elif transform == "extract_price":
                if result is None:
                    continue
                if not isinstance(result, str):
                    result = str(result)
                result = re.sub(r"[^0-9,.\-]", "", result)
            elif transform == "comma_to_dot":
                if isinstance(result, str):
                    # Удаляем любые пробелы/неразрывные пробелы перед заменой запятой на точку
                    result = re.sub(r"\s+", "", result).replace(",", ".")
                elif isinstance(result, (int, float)):
                    result = str(result)
            elif transform == "strip_percent":
                if isinstance(result, str):
                    result = result.replace("%", "").strip()
            elif transform == "to_string":
                if result is not None:
                    result = str(result)
            elif transform == "format_price":
                try:
                    numeric = float(result)
                except (TypeError, ValueError):
                    return None
                result = f"{numeric:.2f}"
            elif transform == "dot_to_comma":
                if isinstance(result, (int, float)):
                    result = str(result)
                if isinstance(result, str):
                    result = result.replace(".", ",")
            elif transform == "append_percent":
                if result is None:
                    continue
                if not isinstance(result, str):
                    result = str(result)
                if not result.endswith("%"):
                    result = f"{result}%"
            elif transform == "normalize_slash_path":
                if isinstance(result, str):
                    fragments = [frag.strip() for frag in result.split("/") if frag.strip()]
                    result = "/".join(fragments)
        return result

    def _is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return value.strip() == ""
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False
