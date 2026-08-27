"""Helpers to keep LinkedIn session secrets out of logs and API responses."""

from __future__ import annotations

from typing import Iterable

from pydantic import SecretStr

# Cookie / token-shaped substrings that must never leave the process.
_SECRET_PATTERNS = (
    "li_at=",
    "JSESSIONID=",
    "jsessionid=",
    "csrf-token",
)


def plain_secret(value: SecretStr | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        return (value.get_secret_value() or "").strip()
    return str(value).strip()


def collect_secrets(*values: SecretStr | str | None) -> list[str]:
    """Return unique secret strings long enough to redact safely."""
    found: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = plain_secret(value)
        if not text:
            continue
        candidates = {text, text.strip('"')}
        for candidate in candidates:
            if len(candidate) < 4 or candidate in seen:
                continue
            seen.add(candidate)
            found.append(candidate)
    # Longest first so partial overlaps redact cleanly.
    found.sort(key=len, reverse=True)
    return found


def redact(text: str, secrets: Iterable[str] | None = None) -> str:
    """Replace known secret values in ``text`` with ``[REDACTED]``."""
    if not text:
        return text
    out = text
    for secret in secrets or ():
        if secret and secret in out:
            out = out.replace(secret, "[REDACTED]")
    # Belt-and-suspenders: never echo cookie assignment fragments.
    lowered = out.lower()
    for marker in _SECRET_PATTERNS:
        if marker.lower() in lowered:
            out = "[REDACTED: response contained session material]"
            break
    return out
