"""Pydantic models that validate declarative JSON mapping documents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    to: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$", max_length=128)
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
    fields: list[FieldMapping] = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def unique_output_keys(self) -> MappingDocument:
        seen: set[str] = set()
        dupes: list[str] = []
        paths = [field.to for field in self.fields]
        for path in paths:
            if path in seen:
                dupes.append(path)
            seen.add(path)
        if dupes:
            raise ValueError(f"Duplicate output field names: {', '.join(dupes)}")
        for path in paths:
            for other in paths:
                if path != other and other.startswith(f"{path}."):
                    raise ValueError(
                        f"Output path '{path}' conflicts with nested key '{other}'."
                    )
        return self
