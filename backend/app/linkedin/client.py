"""Direct HTTP client for LinkedIn's internal Voyager APIs.

No browser is involved: no Playwright, Selenium, Puppeteer, or HTML scraping.
Profile data is fetched with GET requests to /voyager/api/... using session cookies.
curl_cffi is an HTTP client (libcurl) used only to match a common TLS fingerprint;
it does not launch Chrome or render pages.

Read-only by design: this client never POSTs/PUTs/PATCHes/DELETEs to LinkedIn,
so a caller of this API cannot edit the operator's LinkedIn profile via the session.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import quote, urlparse

from curl_cffi.requests import AsyncSession

from app.exceptions import (
    LinkedInError,
    LinkedInRateLimitError,
    NotConfiguredError,
    ProfileNotFoundError,
    SessionExpiredError,
)
from app.linkedin.merge import merge_section_payloads

logger = logging.getLogger(__name__)

BASE = "https://www.linkedin.com/voyager/api"
ALLOWED_HOST = "www.linkedin.com"
# Only identity profile *read* paths — never profile update / messaging / posts.
_ALLOWED_PATH_RE = re.compile(
    r"^/voyager/api/identity/"
    r"(?:dash/profiles|profiles/[^/]+/(?:profileView|skills|skillCategory|"
    r"certifications|languages|honors|volunteerExperiences))"
    r"(?:\?.*)?$"
)
_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE", "CONNECT", "TRACE"})

FALLBACK_DECORATIONS = [
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93",
    "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-35",
    "com.linkedin.voyager.dash.deco.identity.profile.WebFullProfile-1",
]

# Extra Rest.li GETs the website fires for profile sections that the dash
# decoration often omits or truncates. Still HTTP-only — never a browser.
SECTION_PATHS = (
    ("skillView", "identity/profiles/{id}/skills"),
    ("skillCategoryView", "identity/profiles/{id}/skillCategory"),
    ("certificationView", "identity/profiles/{id}/certifications"),
    ("languageView", "identity/profiles/{id}/languages"),
    ("honorView", "identity/profiles/{id}/honors"),
    ("volunteerExperienceView", "identity/profiles/{id}/volunteerExperiences"),
)

TRACK = {
    "clientVersion": "1.13.33333",
    "mpVersion": "1.13.33333",
    "osName": "web",
    "timezoneOffset": 0,
    "timezone": "UTC",
    "deviceFormFactor": "DESKTOP",
    "mpName": "voyager-web",
    "displayWidth": 1920,
    "displayHeight": 1080,
}


def assert_read_only_url(url: str) -> None:
    """Reject anything that is not a LinkedIn Voyager profile *read* URL."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != ALLOWED_HOST:
        raise LinkedInError("Blocked non-LinkedIn or non-HTTPS upstream URL.")
    path_qs = parsed.path
    if parsed.query:
        path_qs = f"{parsed.path}?{parsed.query}"
    if not _ALLOWED_PATH_RE.match(path_qs):
        raise LinkedInError("Blocked upstream path outside read-only profile endpoints.")


class ReadOnlyAsyncSession:
    """Wraps curl_cffi AsyncSession and refuses every mutating HTTP method."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get(self, url: str, **kwargs: Any) -> Any:
        assert_read_only_url(url)
        return await self._session.get(url, **kwargs)

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        verb = (method or "").upper()
        if verb in _MUTATING_METHODS or verb != "GET":
            raise LinkedInError(
                f"Blocked {verb or 'unknown'} to LinkedIn — this client is read-only."
            )
        assert_read_only_url(url)
        return await self._session.request("GET", url, **kwargs)

    async def post(self, *args: Any, **kwargs: Any) -> Any:
        raise LinkedInError("Blocked POST to LinkedIn — this client is read-only.")

    async def put(self, *args: Any, **kwargs: Any) -> Any:
        raise LinkedInError("Blocked PUT to LinkedIn — this client is read-only.")

    async def patch(self, *args: Any, **kwargs: Any) -> Any:
        raise LinkedInError("Blocked PATCH to LinkedIn — this client is read-only.")

    async def delete(self, *args: Any, **kwargs: Any) -> Any:
        raise LinkedInError("Blocked DELETE to LinkedIn — this client is read-only.")

    async def close(self) -> None:
        await self._session.close()


class LinkedInClient:
    """Read-only Voyager client. Public surface is ``fetch_profile`` only."""

    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        decoration_id: str,
        extra_cookies: dict[str, str] | None = None,
        user_agent: str = "",
    ):
        self.li_at = (li_at or "").strip()
        csrf = (jsessionid or "").strip().strip('"')
        self.csrf = csrf
        self.decoration_id = decoration_id
        self.user_agent = (user_agent or "").strip()
        self.extra_cookies = {
            key: value.strip()
            for key, value in (extra_cookies or {}).items()
            if key and (value or "").strip()
        }
        self._session: ReadOnlyAsyncSession | None = None

    def __repr__(self) -> str:
        # Never print session cookies if the client is logged or raised in a debugger.
        extra = sorted(self.extra_cookies)
        return (
            f"LinkedInClient(configured={self.configured!r}, "
            f"decoration_id={self.decoration_id!r}, extra_cookies={extra!r})"
        )

    @property
    def configured(self) -> bool:
        return bool(self.li_at and self.csrf)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _headers(self, public_id: str) -> dict[str, str]:
        # Accept + CSRF for GET only. No content-type / write headers.
        headers = {
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "accept-language": "en-US,en;q=0.9",
            "csrf-token": self.csrf,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
            "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base;1",
            "x-li-track": json.dumps(TRACK, separators=(",", ":")),
            "referer": f"https://www.linkedin.com/in/{public_id}/",
        }
        if self.user_agent:
            # Same browser string that minted li_at — LinkedIn is picky when they diverge.
            headers["user-agent"] = self.user_agent
        return headers

    def _cookies(self) -> dict[str, str]:
        jsid = self.csrf if self.csrf.startswith('"') else f'"{self.csrf}"'
        cookies = {
            "li_at": self.li_at,
            "JSESSIONID": jsid,
        }
        cookies.update(self.extra_cookies)
        return cookies

    async def _session_get(self) -> ReadOnlyAsyncSession:
        if self._session is None:
            # HTTP-only: impersonate sets TLS/JA3, it does not start a browser.
            raw = AsyncSession(impersonate="chrome", timeout=30)
            self._session = ReadOnlyAsyncSession(raw)
        return self._session

    async def fetch_profile(self, public_id: str) -> dict[str, Any]:
        if not self.configured:
            raise NotConfiguredError()

        decorations = [self.decoration_id]
        for deco in FALLBACK_DECORATIONS:
            if deco not in decorations:
                decorations.append(deco)

        last_error: Exception | None = None
        payload: dict[str, Any] | None = None
        for decoration_id in decorations:
            try:
                candidate = await self._get_dash_profile(public_id, decoration_id)
                if _has_profile_data(candidate):
                    payload = candidate
                    break
            except (SessionExpiredError, LinkedInRateLimitError, ProfileNotFoundError):
                raise
            except LinkedInError as exc:
                last_error = exc
                logger.info("Dash profile fetch failed for %s (%s): %s", public_id, decoration_id, exc)
                continue

        if payload is None:
            try:
                payload = await self._get_profile_view(public_id)
            except LinkedInError:
                if last_error:
                    raise last_error
                raise

        sections = await self._fetch_profile_sections(public_id)
        return merge_section_payloads(payload, sections)

    async def _fetch_profile_sections(self, public_id: str) -> dict[str, dict[str, Any] | None]:
        encoded_id = quote(public_id, safe="")
        keys = [key for key, _path in SECTION_PATHS]
        responses = await asyncio.gather(
            *(
                self._get_json(
                    f"{BASE}/{path.format(id=encoded_id)}",
                    public_id,
                    optional=True,
                )
                for _key, path in SECTION_PATHS
            )
        )
        return dict(zip(keys, responses))

    async def _get_dash_profile(self, public_id: str, decoration_id: str) -> dict[str, Any]:
        encoded_id = quote(public_id, safe="")
        encoded_deco = quote(decoration_id, safe="")
        url = (
            f"{BASE}/identity/dash/profiles"
            f"?q=memberIdentity&memberIdentity={encoded_id}"
            f"&decorationId={encoded_deco}"
        )
        payload = await self._get_json(url, public_id)
        assert payload is not None
        return payload

    async def _get_profile_view(self, public_id: str) -> dict[str, Any]:
        encoded_id = quote(public_id, safe="")
        url = f"{BASE}/identity/profiles/{encoded_id}/profileView"
        payload = await self._get_json(url, public_id)
        assert payload is not None
        return payload

    async def _get_json(
        self,
        url: str,
        public_id: str,
        *,
        optional: bool = False,
    ) -> dict[str, Any] | None:
        # Hard read-only gate before any network I/O.
        assert_read_only_url(url)
        session = await self._session_get()
        try:
            response = await session.get(
                url,
                headers=self._headers(public_id),
                cookies=self._cookies(),
                allow_redirects=False,
            )
        except LinkedInError:
            raise
        except Exception as exc:  # network / TLS
            if optional:
                logger.info("Optional Voyager request failed for %s (%s)", public_id, type(exc).__name__)
                return None
            # Do not interpolate exception text — it can include request headers/cookies.
            raise LinkedInError("Failed to reach LinkedIn.") from exc

        status = response.status_code
        if status in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            if "login" in location.lower() or "uas/login" in location.lower():
                if optional:
                    return None
                raise SessionExpiredError()
            if optional:
                return None
            raise LinkedInError(f"LinkedIn redirected the request ({status}).")

        if status in (401, 403):
            if optional:
                return None
            raise SessionExpiredError()
        if status == 429:
            if optional:
                logger.info("LinkedIn rate-limited optional request %s", url)
                return None
            raise LinkedInRateLimitError()
        if status == 404:
            if optional:
                return None
            raise ProfileNotFoundError()
        if status >= 500:
            if optional:
                return None
            raise LinkedInError(f"LinkedIn returned HTTP {status}.")
        if status >= 400:
            if optional:
                return None
            # Never echo upstream response bodies — they can contain session material.
            raise LinkedInError(f"LinkedIn rejected the request (HTTP {status}).")

        try:
            payload = response.json()
        except Exception as exc:
            if optional:
                return None
            raise LinkedInError("LinkedIn returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            if optional:
                return None
            raise LinkedInError("LinkedIn returned an unexpected payload.")
        return payload


def _has_profile_data(payload: dict[str, Any]) -> bool:
    if payload.get("profile"):
        return True
    included = payload.get("included") or []
    if any(isinstance(item, dict) and item.get("firstName") for item in included):
        return True
    elements = (payload.get("data") or {}).get("elements") if isinstance(payload.get("data"), dict) else None
    return bool(elements)
