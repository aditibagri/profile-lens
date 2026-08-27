"""Pydantic models that validate declarative JSON mapping documents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContextSelector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_: str = Field(alias="from")
    index: int | None = None
    fallbackIndex: int | None = None
    where: dict[str, Any] = Field(default_factory=dict)
    # Skip another context alias (e.g. previous job skips $currentJob).
    skip: str | None = None


class FieldMapping(BaseModel):
    """One output field. Edit mappings/*.json — not Python — to change the schema."""

    model_config = ConfigDict(extra="forbid")

    to: str
    from_: str = Field(alias="from")
    pluck: str | list[str] | None = None
    join: str | None = None
    itemFormat: str | None = None
    transform: Literal["dateRange", "count"] | None = None


class MappingDocument(BaseModel):
    """JSON conversion schema: context aliases + field projections."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    description: str = ""
    context: dict[str, ContextSelector] = Field(default_factory=dict)
    fields: list[FieldMapping]
