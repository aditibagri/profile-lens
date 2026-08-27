"""Direct HTTP client for LinkedIn's internal Voyager APIs.

No browser is involved: no Playwright, Selenium, Puppeteer, or HTML scraping.
Profile data is fetched with GET requests to /voyager/api/... using session cookies.
curl_cffi is an HTTP client (libcurl) used only to match a common TLS fingerprint;
it does not launch Chrome or render pages.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import quote

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


class LinkedInClient:
    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        decoration_id: str,
        extra_cookies: dict[str, str] | None = None,
    ):
        self.li_at = (li_at or "").strip()
        csrf = (jsessionid or "").strip().strip('"')
        self.csrf = csrf
        self.decoration_id = decoration_id
        self.extra_cookies = {
            key: value.strip()
            for key, value in (extra_cookies or {}).items()
            if key and (value or "").strip()
        }
        self._session: AsyncSession | None = None

    @property
    def configured(self) -> bool:
        return bool(self.li_at and self.csrf)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _headers(self, public_id: str) -> dict[str, str]:
        return {
            "accept": "application/vnd.linkedin.normalized+json+2.1",
            "accept-language": "en-US,en;q=0.9",
            "csrf-token": self.csrf,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
            "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base;1",
            "x-li-track": json.dumps(TRACK, separators=(",", ":")),
            "referer": f"https://www.linkedin.com/in/{public_id}/",
        }

    def _cookies(self) -> dict[str, str]:
        jsid = self.csrf if self.csrf.startswith('"') else f'"{self.csrf}"'
        cookies = {
            "li_at": self.li_at,
            "JSESSIONID": jsid,
        }
        cookies.update(self.extra_cookies)
        return cookies

    async def _session_get(self) -> AsyncSession:
        if self._session is None:
            # HTTP-only: impersonate sets TLS/JA3, it does not start a browser.
            self._session = AsyncSession(impersonate="chrome", timeout=30)
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
        session = await self._session_get()
        try:
            response = await session.get(
                url,
                headers=self._headers(public_id),
                cookies=self._cookies(),
                allow_redirects=False,
            )
        except Exception as exc:  # network / TLS
            if optional:
                logger.info("Optional Voyager request failed for %s: %s", url, exc)
                return None
            raise LinkedInError(f"Failed to reach LinkedIn: {exc}") from exc

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
            snippet = (response.text or "")[:240]
            raise LinkedInError(f"LinkedIn rejected the request (HTTP {status}): {snippet}")

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
