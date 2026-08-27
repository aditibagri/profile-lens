from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request

from app.adapters import DEFAULT_ADAPTER, get_adapter, list_adapters
from app.exceptions import LinkedInError
from app.linkedin.parser import parse_profile
from app.linkedin.urls import extract_public_id
from app.schemas import (
    AdaptedProfileResponse,
    AdapterInfo,
    ProfileRequest,
    ProfileResponse,
)

router = APIRouter(prefix="/v1", tags=["profile"])


def require_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = getattr(request.app.state.settings, "api_key_value", "") or ""
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise LinkedInError(
            "Missing or invalid X-API-Key.",
            status_code=401,
            code="unauthorized",
        )


@router.get(
    "/adapters",
    response_model=list[AdapterInfo],
    summary="List JSON schema adapters available for /v1/profile",
)
async def get_adapters() -> list[AdapterInfo]:
    return [
        AdapterInfo(name=adapter.name, description=adapter.description)
        for adapter in list_adapters()
    ]


@router.post(
    "/profile",
    response_model=AdaptedProfileResponse,
    summary="Resolve a LinkedIn profile URL into structured JSON",
)
async def post_profile(
    body: ProfileRequest,
    request: Request,
    adapter: str = Query(
        DEFAULT_ADAPTER,
        description="Schema adapter: default (nested) or profilelens (flat export).",
    ),
    _: None = Depends(require_api_key),
) -> AdaptedProfileResponse:
    return await _lookup(request, body.url, adapter)


@router.get(
    "/profile",
    response_model=AdaptedProfileResponse,
    summary="Resolve a LinkedIn profile URL (query param, convenient for demos)",
)
async def get_profile(
    request: Request,
    url: str = Query(..., description="Public LinkedIn profile URL"),
    adapter: str = Query(
        DEFAULT_ADAPTER,
        description="Schema adapter: default (nested) or profilelens (flat export).",
    ),
    _: None = Depends(require_api_key),
) -> AdaptedProfileResponse:
    return await _lookup(request, url, adapter)


async def _lookup(request: Request, url: str, adapter_name: str) -> AdaptedProfileResponse:
    schema_adapter = get_adapter(adapter_name)
    public_id = extract_public_id(url)
    canonical = f"https://www.linkedin.com/in/{public_id}/"

    cached = request.app.state.cache.get(public_id)
    if cached is not None:
        return AdaptedProfileResponse(
            adapter=schema_adapter.name,
            data=schema_adapter.adapt(cached),
        )

    if not request.app.state.limiter.allow():
        retry_after = request.app.state.limiter.retry_after()
        raise LinkedInError(
            f"Too many LinkedIn fetches from this server. Retry after {retry_after}s.",
            status_code=429,
            code="rate_limited",
        )

    payload = await request.app.state.linkedin.fetch_profile(public_id)
    if not payload:
        raise LinkedInError("LinkedIn returned an empty profile payload.")

    profile = parse_profile(payload, public_id, canonical)
    if not profile.fullName and not profile.headline and not profile.experience:
        raise LinkedInError(
            "Could not parse profile fields from LinkedIn's response.",
            status_code=502,
            code="parse_error",
        )

    request.app.state.cache.set(public_id, profile)
    return AdaptedProfileResponse(
        adapter=schema_adapter.name,
        data=schema_adapter.adapt(profile),
    )
