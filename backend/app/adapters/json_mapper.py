"""Apply a declarative JSON mapping document to a nested profile dict.

This is the maintainable alternative to hand-written Python / jq / JSONata:
edit ``adapters/mappings/*.json`` to change the output shape. The mapping file
is validated by ``MappingDocument`` (a JSON-schema-like contract).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.adapters.mapping_schema import ContextSelector, FieldMapping, MappingDocument

MAPPINGS_DIR = Path(__file__).resolve().parent / "mappings"


def _dig(data: Any, path: str) -> Any:
    cur = data
    if not path:
        return cur
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _matches(item: Any, where: dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False
    for path, expected in where.items():
        if _dig(item, path) != expected:
            return False
    return True


def _resolve_context(
    root: dict[str, Any],
    selector: ContextSelector,
    resolved: dict[str, Any],
) -> Any:
    collection = _dig(root, selector.from_) or []
    if not isinstance(collection, list):
        return None

    if selector.skip:
        skip_value = resolved.get(selector.skip)
        collection = [item for item in collection if item is not skip_value]

    if selector.where:
        for item in collection:
            if _matches(item, selector.where):
                return item
        if selector.fallbackIndex is not None and 0 <= selector.fallbackIndex < len(collection):
            return collection[selector.fallbackIndex]
        return None

    if selector.index is not None:
        if 0 <= selector.index < len(collection):
            return collection[selector.index]
        return None

    return collection[0] if collection else None


def _resolve_from(path: str, root: dict[str, Any], context: dict[str, Any]) -> Any:
    if path.startswith("$"):
        # $alias or $alias.nested.path
        rest = path[1:]
        alias, _, nested = rest.partition(".")
        base = context.get(alias)
        return _dig(base, nested) if nested else base
    return _dig(root, path)


def _format_date_range(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start") or ""
    end = "Present" if value.get("current") else (value.get("end") or "")
    if start and end:
        return f"{start} – {end}"
    return start or end or None


def _pluck_join(value: Any, field: FieldMapping) -> Any:
    if not isinstance(value, list):
        return "" if field.join is not None else None

    pluck = field.pluck
    parts: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        if isinstance(pluck, list):
            fmt = field.itemFormat or " ".join(f"{{{name}}}" for name in pluck)
            data = {name: item.get(name) for name in pluck}
            # Drop empty parentheticals when proficiency is missing.
            if "proficiency" in data and not data["proficiency"]:
                parts.append(str(data.get("name") or ""))
            else:
                parts.append(fmt.format(**{k: (v or "") for k, v in data.items()}))
        elif isinstance(pluck, str):
            extracted = item.get(pluck)
            if extracted is not None:
                parts.append(str(extracted))
        else:
            parts.append(str(item))

    parts = [p for p in parts if p]
    if field.join is not None:
        return field.join.join(parts)
    return parts


def _apply_field(field: FieldMapping, root: dict[str, Any], context: dict[str, Any]) -> Any:
    value = _resolve_from(field.from_, root, context)

    if field.transform == "count":
        return len(value) if isinstance(value, list) else 0
    if field.transform == "dateRange":
        return _format_date_range(value)
    if field.pluck is not None or field.join is not None:
        return _pluck_join(value, field)
    return value


def apply_mapping(document: MappingDocument, root: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {}
    for name, selector in document.context.items():
        context[name] = _resolve_context(root, selector, context)
    return {field.to: _apply_field(field, root, context) for field in document.fields}


@lru_cache(maxsize=16)
def load_mapping(name: str) -> MappingDocument:
    path = MAPPINGS_DIR / f"{name}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MappingDocument.model_validate(raw)


def project_with_mapping(name: str, root: dict[str, Any]) -> dict[str, Any]:
    return apply_mapping(load_mapping(name), root)
