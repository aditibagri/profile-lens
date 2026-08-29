"""Registry of available profile schema adapters."""

from __future__ import annotations

from app.adapters.base import ProfileSchemaAdapter
from app.adapters.custom import CustomProfileAdapter
from app.adapters.file_adapter import JsonMappingAdapter
from app.adapters.json_mapper import list_mapping_names
from app.adapters.mapping_schema import MappingDocument
from app.exceptions import LinkedInError

DEFAULT_ADAPTER = "profilelens"


def _file_adapters() -> dict[str, ProfileSchemaAdapter]:
    names = list_mapping_names()
    if DEFAULT_ADAPTER not in names:
        raise RuntimeError("Required mapping file missing: adapters/mappings/profilelens.json")
    return {name: JsonMappingAdapter(name) for name in names}


_ADAPTERS: dict[str, ProfileSchemaAdapter] = {
    **_file_adapters(),
    CustomProfileAdapter.name: CustomProfileAdapter(),
}


def list_adapters() -> list[ProfileSchemaAdapter]:
    ordered = [adapter for adapter in _ADAPTERS.values() if adapter.name != CustomProfileAdapter.name]
    ordered.append(_ADAPTERS[CustomProfileAdapter.name])
    return ordered


def get_adapter(
    name: str | None,
    mapping: MappingDocument | None = None,
) -> ProfileSchemaAdapter:
    key = (name or DEFAULT_ADAPTER).strip().lower()
    if key == CustomProfileAdapter.name:
        if mapping is None:
            raise LinkedInError(
                "adapter=custom requires a schema object in the JSON body "
                '({ "fields": [{ "to": "name", "from": "fullName" }] }).',
                status_code=400,
                code="invalid_schema",
            )
        return CustomProfileAdapter(mapping)

    adapter = _ADAPTERS.get(key)
    if adapter is None:
        available = ", ".join(sorted(_ADAPTERS))
        raise LinkedInError(
            f"Unknown adapter '{name}'. Available: {available}",
            status_code=400,
            code="invalid_adapter",
        )
    return adapter
