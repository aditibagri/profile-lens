"""Adapters whose output shape is declared in ``mappings/<name>.json``."""

from __future__ import annotations

from typing import Any

from app.adapters.json_mapper import load_mapping, project_with_mapping
from app.schemas import ProfileResponse


class JsonMappingAdapter:
    """Project the canonical profile through a JSON mapping file of the same name."""

    def __init__(self, name: str):
        self.name = name

    @property
    def description(self) -> str:
        doc = load_mapping(self.name)
        return doc.description or f"JSON mapping `{self.name}`."

    def adapt(self, profile: ProfileResponse) -> dict[str, Any]:
        return project_with_mapping(self.name, profile.model_dump(mode="json"))
