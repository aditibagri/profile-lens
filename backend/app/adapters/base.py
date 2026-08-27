"""Schema adapters turn the canonical profile model into different JSON shapes."""

from __future__ import annotations

from typing import Any, Protocol

from app.schemas import ProfileResponse


class ProfileSchemaAdapter(Protocol):
    """Convert the internal profile model into a public JSON schema."""

    name: str
    description: str

    def adapt(self, profile: ProfileResponse) -> dict[str, Any]:
        """Return a JSON-serializable dict in this adapter's schema."""
        ...
