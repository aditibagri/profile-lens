"""Merge extra Voyager section payloads into the primary profile JSON.

Section endpoints return the same Rest.li shapes as the website XHR calls
(normalized `included` graphs and/or `{elements: [...]}` views). Nothing here
parses HTML.
"""

from __future__ import annotations

from typing import Any


def merge_section_payloads(
    primary: dict[str, Any],
    sections: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    merged = dict(primary)
    included = [item for item in (merged.get("included") or []) if isinstance(item, dict)]

    for view_key, payload in sections.items():
        if not isinstance(payload, dict):
            continue

        extra_included = payload.get("included")
        if isinstance(extra_included, list):
            included.extend(item for item in extra_included if isinstance(item, dict))

        view = _as_collection_view(payload)
        if view is None:
            continue

        if not _view_has_elements(merged.get(view_key)):
            merged[view_key] = view

        for item in view.get("elements") or []:
            if isinstance(item, dict) and item.get("$type"):
                included.append(item)

    merged["included"] = included
    return merged


def _as_collection_view(payload: dict[str, Any]) -> dict[str, Any] | None:
    elements = payload.get("elements")
    if isinstance(elements, list):
        return {"elements": [item for item in elements if isinstance(item, dict)]}

    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("elements"), list):
        return {
            "elements": [item for item in data["elements"] if isinstance(item, dict)],
        }
    if isinstance(data, list):
        return {"elements": [item for item in data if isinstance(item, dict)]}
    return None


def _view_has_elements(view: Any) -> bool:
    if not isinstance(view, dict):
        return False
    elements = view.get("elements") or []
    return any(isinstance(item, dict) for item in elements)
