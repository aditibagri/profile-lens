from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.exceptions import SessionExpiredError
from app.main import create_app


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def test_create_app_passes_extra_cookies() -> None:
    settings = Settings(
        linkedin_li_at="tok",
        linkedin_jsessionid="ajax:9",
        linkedin_liap="true",
        linkedin_bcookie="v=2",
        api_key="",
    )
    with TestClient(create_app(settings)) as client:
        cookies = client.app.state.linkedin._cookies()
        assert cookies["liap"] == "true"
        assert cookies["bcookie"] == "v=2"
        assert cookies["li_at"] == "tok"


def test_health_reports_cookie_presence() -> None:
    empty = Settings(linkedin_li_at="", linkedin_jsessionid="", api_key="")
    with _client(empty) as client:
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["linkedinConfigured"] is False

    configured = Settings(linkedin_li_at="x", linkedin_jsessionid="ajax:1")
    with _client(configured) as client:
        assert client.get("/health").json()["linkedinConfigured"] is True


def test_ui_home_and_config() -> None:
    settings = Settings(linkedin_li_at="x", linkedin_jsessionid="ajax:1", api_key="secret")
    with _client(settings) as client:
        home = client.get("/")
        assert home.status_code == 200
        assert "text/html" in home.headers["content-type"]
        assert b"Profile Lens" in home.content
        assert b"vue" in home.content.lower()
        assert b"fetchProfile" in client.get("/js/api.js").content
        assert b"createApp" in client.get("/js/app.js").content
        assert client.get("/css/styles.css").status_code == 200

        cfg = client.get("/ui/config")
        assert cfg.status_code == 200
        body = cfg.json()
        assert body["apiKeyRequired"] is True
        assert body["linkedinConfigured"] is True
        assert body["defaultAdapter"] == "default"
        names = {a["name"] for a in body["adapters"]}
        assert names == {"default", "profilelens"}


def test_list_adapters() -> None:
    settings = Settings(linkedin_li_at="x", linkedin_jsessionid="ajax:1", api_key="")
    with _client(settings) as client:
        response = client.get("/v1/adapters")
        assert response.status_code == 200
        names = {row["name"] for row in response.json()}
        assert names == {"default", "profilelens"}


def test_invalid_url_returns_400(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/company/google"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_url"


def test_missing_api_key_returns_401(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"


def test_post_profile_success(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["adapter"] == "default"
        data = body["data"]
        assert data["fullName"] == "Ada Lovelace"
        assert data["publicId"] == "ada-lovelace"
        assert data["experience"][0]["company"] == "Analytical Engine Co."
        assert len(data["skills"]) == 2
        client.app.state.linkedin.fetch_profile.assert_awaited_once_with("ada-lovelace")


def test_post_profile_profilelens_adapter(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile?adapter=profilelens",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["adapter"] == "profilelens"
        data = body["data"]
        assert data["fullName"] == "Ada Lovelace"
        assert data["companyName"] == "Analytical Engine Co."
        assert data["jobTitle"] == "Analyst"
        assert "Mathematics" in data["linkedinSkillsLabel"]
        assert isinstance(data["experienceJson"], list)


def test_unknown_adapter_returns_400(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile?adapter=nope",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_adapter"


def test_get_profile_uses_cache(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        mock = AsyncMock(return_value=dash_payload)
        client.app.state.linkedin.fetch_profile = mock
        headers = {"X-API-Key": "test-key"}
        url = "https://www.linkedin.com/in/ada-lovelace/"

        first = client.get("/v1/profile", params={"url": url}, headers=headers)
        second = client.get("/v1/profile", params={"url": url, "adapter": "profilelens"}, headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["fullName"] == "Ada Lovelace"
        assert second.json()["adapter"] == "profilelens"
        assert second.json()["data"]["companyName"] == "Analytical Engine Co."
        mock.assert_awaited_once()


def test_session_expired_maps_to_401(settings: Settings) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(side_effect=SessionExpiredError())
        response = client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "session_expired"
