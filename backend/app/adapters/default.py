"""Default nested profile schema (canonical API shape)."""

from __future__ import annotations

from typing import Any

from app.schemas import ProfileResponse


class DefaultProfileAdapter:
    name = "default"
    description = (
        "Nested profile schema with full experience, education, skills, "
        "certifications, languages, volunteer, and honors arrays."
    )

    def adapt(self, profile: ProfileResponse) -> dict[str, Any]:
        return profile.model_dump(mode="json")
