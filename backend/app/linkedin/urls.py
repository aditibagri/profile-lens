"""Extract a public LinkedIn profile slug from a URL."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

from app.exceptions import InvalidProfileUrlError

_ALLOWED_HOSTS = {"linkedin.com", "www.linkedin.com", "linkedin.cn", "www.linkedin.cn"}
_PROFILE_PATH = re.compile(r"^/in/(?P<slug>[^/?#]+)/?", re.IGNORECASE)


def extract_public_id(profile_url: str) -> str:
    """Return the vanity slug from a LinkedIn profile URL.

    Accepts:
      https://www.linkedin.com/in/williamhgates/
      https://linkedin.com/in/williamhgates
      www.linkedin.com/in/williamhgates?trk=...
    """
    if not profile_url or not str(profile_url).strip():
        raise InvalidProfileUrlError()

    raw = str(profile_url).strip()
    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        bare_host = host[4:]
    else:
        bare_host = host

    if host not in _ALLOWED_HOSTS and bare_host not in {"linkedin.com", "linkedin.cn"}:
        raise InvalidProfileUrlError(
            "URL must be a linkedin.com profile (https://www.linkedin.com/in/{slug})."
        )

    match = _PROFILE_PATH.match(parsed.path or "")
    if not match:
        raise InvalidProfileUrlError(
            "URL must point to a person profile: https://www.linkedin.com/in/{slug}"
        )

    slug = unquote(match.group("slug")).strip().strip("/")
    if not slug or "/" in slug:
        raise InvalidProfileUrlError()

    return slug
