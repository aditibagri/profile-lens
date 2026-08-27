import pytest

from app.exceptions import LinkedInError
from app.linkedin.client import (
    LinkedInClient,
    ReadOnlyAsyncSession,
    assert_read_only_url,
)


def test_assert_read_only_url_allows_profile_gets() -> None:
    assert_read_only_url(
        "https://www.linkedin.com/voyager/api/identity/dash/profiles"
        "?q=memberIdentity&memberIdentity=ada&decorationId=deco"
    )
    assert_read_only_url(
        "https://www.linkedin.com/voyager/api/identity/profiles/ada/profileView"
    )
    assert_read_only_url(
        "https://www.linkedin.com/voyager/api/identity/profiles/ada/skills"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.linkedin.com/voyager/api/identity/profiles/ada/profileEdit",
        "https://www.linkedin.com/voyager/api/identity/dash/profileEdit",
        "https://www.linkedin.com/voyager/api/messaging/conversations",
        "https://www.linkedin.com/voyager/api/voyagerIdentityDashProfileActions",
        "http://www.linkedin.com/voyager/api/identity/profiles/ada/profileView",
        "https://evil.example/voyager/api/identity/profiles/ada/profileView",
        "https://www.linkedin.com/in/ada/",
    ],
)
def test_assert_read_only_url_blocks_writes_and_other_hosts(url: str) -> None:
    with pytest.raises(LinkedInError, match="Blocked"):
        assert_read_only_url(url)


@pytest.mark.asyncio
async def test_read_only_session_blocks_mutating_verbs() -> None:
    class _Dummy:
        async def get(self, *a, **k):  # pragma: no cover
            raise AssertionError("should not get")

        async def request(self, *a, **k):  # pragma: no cover
            raise AssertionError("should not request")

        async def close(self):
            return None

    session = ReadOnlyAsyncSession(_Dummy())  # type: ignore[arg-type]
    url = "https://www.linkedin.com/voyager/api/identity/profiles/ada/profileView"
    for method in ("post", "put", "patch", "delete"):
        with pytest.raises(LinkedInError, match="read-only"):
            await getattr(session, method)(url)
    with pytest.raises(LinkedInError, match="read-only"):
        await session.request("POST", url)
    with pytest.raises(LinkedInError, match="read-only"):
        await session.request("PUT", url)


def test_public_client_surface_is_fetch_only() -> None:
    """API consumers only get fetch_profile — no update/delete helpers."""
    public = {
        name
        for name in dir(LinkedInClient)
        if not name.startswith("_") and callable(getattr(LinkedInClient, name))
    }
    assert "fetch_profile" in public
    assert "close" in public
    for forbidden in (
        "update_profile",
        "edit_profile",
        "delete_profile",
        "post",
        "put",
        "patch",
        "create",
    ):
        assert forbidden not in public
