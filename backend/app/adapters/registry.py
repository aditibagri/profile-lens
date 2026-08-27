"""Registry of available profile schema adapters."""

from __future__ import annotations

from app.adapters.base import ProfileSchemaAdapter
from app.adapters.default import DefaultProfileAdapter
from app.adapters.profilelens import ProfileLensAdapter
from app.exceptions import LinkedInError

_ADAPTERS: dict[str, ProfileSchemaAdapter] = {
    DefaultProfileAdapter.name: DefaultProfileAdapter(),
    ProfileLensAdapter.name: ProfileLensAdapter(),
}

DEFAULT_ADAPTER = DefaultProfileAdapter.name


def list_adapters() -> list[ProfileSchemaAdapter]:
    return list(_ADAPTERS.values())


def get_adapter(name: str | None) -> ProfileSchemaAdapter:
    key = (name or DEFAULT_ADAPTER).strip().lower()
    adapter = _ADAPTERS.get(key)
    if adapter is None:
        available = ", ".join(sorted(_ADAPTERS))
        raise LinkedInError(
            f"Unknown adapter '{name}'. Available: {available}",
            status_code=400,
            code="invalid_adapter",
        )
    return adapter
