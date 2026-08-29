from app.config import Settings
from app.linkedin.client import LinkedInClient, SECTION_PATHS


def test_extra_cookies_are_included_in_request() -> None:
    client = LinkedInClient(
        "li-at-token",
        "ajax:1",
        "deco",
        extra_cookies={"liap": "true", "bcookie": "v=2&abc", "lidc": "b=VG:123"},
    )
    cookies = client._cookies()
    assert cookies["li_at"] == "li-at-token"
    assert cookies["JSESSIONID"] == '"ajax:1"'
    assert cookies["liap"] == "true"
    assert cookies["bcookie"] == "v=2&abc"
    assert cookies["lidc"] == "b=VG:123"


def test_user_agent_header_when_configured() -> None:
    client = LinkedInClient(
        "li-at-token",
        "ajax:1",
        "deco",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TestBrowser/1.0",
    )
    headers = client._headers("ada-lovelace")
    assert headers["user-agent"] == (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) TestBrowser/1.0"
    )


def test_user_agent_omitted_when_blank() -> None:
    client = LinkedInClient("li-at-token", "ajax:1", "deco")
    assert "user-agent" not in client._headers("ada-lovelace")


def test_blank_extra_cookies_are_omitted() -> None:
    client = LinkedInClient(
        "li-at-token",
        "ajax:1",
        "deco",
        extra_cookies={"liap": "  ", "lidc": "", "li_a": "keep-me"},
    )
    cookies = client._cookies()
    assert "liap" not in cookies
    assert "lidc" not in cookies
    assert cookies["li_a"] == "keep-me"


def test_settings_maps_optional_cookie_env_vars() -> None:
    settings = Settings(
        linkedin_li_at="x",
        linkedin_jsessionid="ajax:1",
        linkedin_liap="true",
        linkedin_bcookie="v=2",
        linkedin_lidc="",
        linkedin_li_a="  ",
    )
    assert settings.extra_linkedin_cookies() == {"liap": "true", "bcookie": "v=2"}


def test_settings_maps_user_agent() -> None:
    settings = Settings(linkedin_user_agent="Mozilla/5.0 Test")
    assert settings.linkedin_user_agent == "Mozilla/5.0 Test"


async def test_fetch_profile_merges_section_endpoints(dash_payload: dict) -> None:
    client = LinkedInClient("li", "ajax:1", "deco")
    requested: list[str] = []

    async def fake_get_json(url: str, public_id: str, *, optional: bool = False):
        requested.append(url)
        if "dash/profiles" in url:
            assert optional is False
            return dash_payload
        if url.endswith("/skills"):
            assert optional is True
            return {"elements": [{"name": "Python", "endorsementCount": 9}]}
        if optional:
            return None
        raise AssertionError(url)

    client._get_json = fake_get_json  # type: ignore[method-assign]
    payload = await client.fetch_profile("ada-lovelace")

    assert payload["skillView"]["elements"][0]["name"] == "Python"
    section_urls = [url for url in requested if "/identity/profiles/ada-lovelace/" in url]
    assert len(section_urls) == len(SECTION_PATHS)
    assert any(url.endswith("/skills") for url in section_urls)
    assert any(url.endswith("/skillCategory") for url in section_urls)
    assert any(url.endswith("/certifications") for url in section_urls)
    assert any(url.endswith("/languages") for url in section_urls)


async def test_optional_section_failures_do_not_fail_profile(dash_payload: dict) -> None:
    client = LinkedInClient("li", "ajax:1", "deco")

    async def fake_get_json(url: str, public_id: str, *, optional: bool = False):
        if "dash/profiles" in url:
            return dash_payload
        if optional:
            return None
        raise AssertionError(url)

    client._get_json = fake_get_json  # type: ignore[method-assign]
    payload = await client.fetch_profile("ada-lovelace")
    assert any(item.get("firstName") == "Ada" for item in payload["included"])
    assert "skillView" not in payload
