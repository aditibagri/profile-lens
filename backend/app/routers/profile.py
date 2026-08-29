from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, Header, Query, Request

from app.adapters import DEFAULT_ADAPTER, get_adapter, list_adapters
from app.exceptions import LinkedInError, NotConfiguredError
from app.linkedin.client import LinkedInClient
from app.linkedin.parser import parse_profile
from app.linkedin.urls import extract_public_id
from app.schemas import (
    AdaptedProfileResponse,
    AdapterInfo,
    LinkedInSessionIn,
    ProfileRequest,
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
    return await _lookup(request, body.url, adapter, body.session)


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
    return await _lookup(request, url, adapter, None)


def _visitor_client(session: LinkedInSessionIn, decoration_id: str) -> LinkedInClient | None:
    li_at = (session.liAt or "").strip()
    jsessionid = (session.jsessionid or "").strip()
    if not li_at or not jsessionid:
        return None
    extras = {
        "liap": session.liap,
        "bcookie": session.bcookie,
        "lidc": session.lidc,
        "li_a": session.liA,
    }
    return LinkedInClient(
        li_at=li_at,
        jsessionid=jsessionid,
        decoration_id=decoration_id,
        extra_cookies=extras,
        user_agent=session.userAgent,
    )


def _session_scope(session: LinkedInSessionIn | None) -> str:
    token = ((session.liAt if session else "") or "").strip()
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _session_secrets(session: LinkedInSessionIn | None) -> list[str]:
    if session is None:
        return []
    values = [
        session.liAt,
        session.jsessionid,
        session.liap,
        session.bcookie,
        session.lidc,
        session.liA,
    ]
    return [item.strip() for item in values if item and item.strip()]


async def _lookup(
    request: Request,
    url: str,
    adapter_name: str,
    visitor_session: LinkedInSessionIn | None,
) -> AdaptedProfileResponse:
    schema_adapter = get_adapter(adapter_name)
    public_id = extract_public_id(url)
    canonical = f"https://www.linkedin.com/in/{public_id}/"
    request.state.redact_secrets = _session_secrets(visitor_session)

    settings = request.app.state.settings
    ephemeral = _visitor_client(visitor_session, settings.decoration_id) if visitor_session else None
    client = ephemeral or request.app.state.linkedin
    scope = _session_scope(visitor_session) if ephemeral else ""

    try:
        cached = request.app.state.cache.get(public_id, scope)
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

        if not client.configured:
            raise NotConfiguredError()

        payload = await client.fetch_profile(public_id)
        if not payload:
            raise LinkedInError("LinkedIn returned an empty profile payload.")

        profile = parse_profile(payload, public_id, canonical)
        if not profile.fullName and not profile.headline and not profile.experience:
            raise LinkedInError(
                "Could not parse profile fields from LinkedIn's response.",
                status_code=502,
                code="parse_error",
            )

        request.app.state.cache.set(public_id, profile, scope)
        return AdaptedProfileResponse(
            adapter=schema_adapter.name,
            data=schema_adapter.adapt(profile),
        )
    finally:
        if ephemeral is not None:
            await ephemeral.close()
