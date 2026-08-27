from __future__ import annotations

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

FRONTEND_DIR = resolve_frontend_dir()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.linkedin = LinkedInClient(
            li_at=settings.linkedin_li_at,
            jsessionid=settings.linkedin_jsessionid,
            decoration_id=settings.decoration_id,
            extra_cookies=settings.extra_linkedin_cookies(),
        )
        app.state.cache = ProfileCache(ttl_seconds=settings.cache_ttl_seconds)
        app.state.limiter = RateLimiter(max_calls=settings.rate_limit_per_minute)
        try:
            yield
        finally:
            await app.state.linkedin.close()

    app = FastAPI(
        title="LinkedIn Profile API",
        version="1.1.0",
        description=(
            "Backend: Voyager HTTP client + schema adapters. "
            "Frontend lives in /frontend and is served separately from API routes."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
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
        return UiConfigResponse(
            apiKeyRequired=bool(settings.api_key),
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
    async def linkedin_error_handler(_request: Request, exc: LinkedInError) -> JSONResponse:
        headers = {}
        if exc.status_code == 429:
            headers["Retry-After"] = "60"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code, "detail": exc.message},
            headers=headers,
        )

    return app


app = create_app()
