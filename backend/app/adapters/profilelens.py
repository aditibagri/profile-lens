"""Flat export adapter driven by ``mappings/profilelens.json``."""

from __future__ import annotations

from typing import Any

from app.adapters.json_mapper import load_mapping, project_with_mapping
from app.schemas import ProfileResponse

MAPPING_NAME = "profilelens"


class ProfileLensAdapter:
    """Flatten nested profile data using the Profile Lens JSON mapping document."""

    name = MAPPING_NAME

    @property
    def description(self) -> str:
        doc = load_mapping(MAPPING_NAME)
        return doc.description or (
            "Profile Lens flat fields plus experienceJson / educationJson for CSV-style consumers."
        )

    def adapt(self, profile: ProfileResponse) -> dict[str, Any]:
        return project_with_mapping(MAPPING_NAME, profile.model_dump(mode="json"))
