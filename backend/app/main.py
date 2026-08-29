from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters import DEFAULT_ADAPTER, list_adapters
from app.cache import ProfileCache
from app.config import Settings, get_settings
from app.exceptions import LinkedInError
from app.linkedin.client import LinkedInClient
from app.paths import resolve_frontend_dir
from app.ratelimit import RateLimiter
from app.routers.profile import router as profile_router
from app.schemas import AdapterInfo, HealthResponse, UiConfigResponse
from app.security import redact

FRONTEND_DIR = resolve_frontend_dir()
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    session = settings.linkedin_session_values()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.linkedin = LinkedInClient(
            li_at=session["li_at"],
            jsessionid=session["jsessionid"],
            decoration_id=settings.decoration_id,
            extra_cookies=settings.extra_linkedin_cookies(),
            user_agent=settings.linkedin_user_agent,
        )
        app.state.cache = ProfileCache(ttl_seconds=settings.cache_ttl_seconds)
        app.state.limiter = RateLimiter(max_calls=settings.rate_limit_per_minute)
        if settings.linkedin_configured and not settings.api_key_value:
            logger.warning(
                "LinkedIn session is configured without API_KEY. "
                "Set API_KEY so strangers cannot spend your session via /v1/profile."
            )
        try:
            yield
        finally:
            await app.state.linkedin.close()

    app = FastAPI(
        title="LinkedIn Profile API",
        version="1.1.0",
        description=(
            "Backend: Voyager HTTP client + schema adapters. "
            "Frontend lives in /frontend and is served separately from API routes. "
            "LinkedIn session cookies never leave the server process."
        ),
        lifespan=lifespan,
    )
    # Same-origin browser clients do not need credentialed CORS; keep credentials off
    # so browsers never attach cookies to cross-origin API calls.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )
    app.include_router(profile_router)

    if FRONTEND_DIR.is_dir():
        app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="frontend-css")
        app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="frontend-js")

        @app.get("/", include_in_schema=False)
        async def ui() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/ui/config", response_model=UiConfigResponse, tags=["ops"])
    async def ui_config() -> UiConfigResponse:
        # Booleans only — never session cookies or API key values.
        return UiConfigResponse(
            apiKeyRequired=bool(settings.api_key_value),
            linkedinConfigured=settings.linkedin_configured,
            adapters=[
                AdapterInfo(name=a.name, description=a.description) for a in list_adapters()
            ],
            defaultAdapter=DEFAULT_ADAPTER,
        )

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            linkedinConfigured=settings.linkedin_configured,
        )

    @app.exception_handler(LinkedInError)
    async def linkedin_error_handler(request: Request, exc: LinkedInError) -> JSONResponse:
        headers = {}
        if exc.status_code == 429:
            headers["Retry-After"] = "60"
        extra = getattr(request.state, "redact_secrets", None) or []
        safe = redact(exc.message, [*settings.secrets_for_redaction(), *extra])
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": safe, "code": exc.code, "detail": safe},
            headers=headers,
        )

    return app


app = create_app()
