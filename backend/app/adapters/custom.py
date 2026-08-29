"""Request-supplied mapping document → custom JSON shape."""

from __future__ import annotations

from typing import Any

from app.adapters.json_mapper import apply_mapping
from app.adapters.mapping_schema import MappingDocument
from app.exceptions import LinkedInError
from app.schemas import ProfileResponse


class CustomProfileAdapter:
    """Project canonical profile JSON using a mapping sent with the request."""

    name = "custom"
    description = (
        "Build your own JSON keys. Send a mapping document in the request body "
        "(`schema`) or paste JSON in the adapter editor on the website."
    )

    def __init__(self, document: MappingDocument | None = None):
        self.document = document

    def adapt(self, profile: ProfileResponse) -> dict[str, Any]:
        if self.document is None:
            raise LinkedInError(
                "Custom schema is missing.",
                status_code=400,
                code="invalid_schema",
            )
        return apply_mapping(self.document, profile.model_dump(mode="json"))
