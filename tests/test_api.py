from unittest.mock import AsyncMock, patch

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
        assert b"Connect your LinkedIn" in home.content
        assert b"schema-builder" in home.content
        assert b"Your adapter JSON" in home.content
        assert b"Profile Lens adapter" in home.content
        assert b"Response adapter" in home.content
        assert b"Save adapter" in home.content
        assert b"From LinkedIn" in home.content
        assert b"jsoneditor" in home.content
        assert b"validateAdapterTemplate" in client.get("/js/schemaEditor.js").content
        assert b"vue" in home.content.lower()
        assert b"fetchProfile" in client.get("/js/api.js").content
        assert b"createApp" in client.get("/js/app.js").content
        assert b"treeToRows" in client.get("/js/schemaEditor.js").content
        assert client.get("/css/styles.css").status_code == 200

        cfg = client.get("/ui/config")
        assert cfg.status_code == 200
        body = cfg.json()
        assert body["apiKeyRequired"] is True
        assert body["linkedinConfigured"] is True
        assert body["defaultAdapter"] == "profilelens"
        names = {a["name"] for a in body["adapters"]}
        assert names == {"profilelens", "custom"}
        assert body["schemaFields"]
        paths = {row["path"] for row in body["schemaFields"]}
        assert "fullName" in paths
        assert "experience.0.title" in paths
        assert "default" not in body["schemaPresets"]
        pl_fields = {row["to"] for row in body["schemaPresets"]["profilelens"]["fields"]}
        assert {"fullName", "companyName", "jobTitle", "experienceJson"} <= pl_fields


def test_list_adapters() -> None:
    settings = Settings(linkedin_li_at="x", linkedin_jsessionid="ajax:1", api_key="")
    with _client(settings) as client:
        response = client.get("/v1/adapters")
        assert response.status_code == 200
        names = {row["name"] for row in response.json()}
        assert names == {"profilelens", "custom"}


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
        assert body["adapter"] == "profilelens"
        data = body["data"]
        assert data["fullName"] == "Ada Lovelace"
        assert data["linkedinProfileSlug"] == "ada-lovelace"
        assert data["companyName"] == "Analytical Engine Co."
        assert data["jobTitle"] == "Analyst"
        assert "Mathematics" in data["linkedinSkillsLabel"]
        assert body["source"]["fullName"] == "Ada Lovelace"
        assert body["source"]["experience"][0]["company"] == "Analytical Engine Co."
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


def test_post_profile_custom_adapter(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile?adapter=custom",
            json={
                "url": "https://www.linkedin.com/in/ada-lovelace/",
                "schema": {
                    "fields": [
                        {"to": "name", "from": "fullName"},
                        {"to": "title", "from": "experience.0.title"},
                    ]
                },
            },
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["adapter"] == "custom"
        assert body["data"] == {"name": "Ada Lovelace", "title": "Analyst"}


def test_post_profile_custom_nested_schema(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile?adapter=custom",
            json={
                "url": "https://www.linkedin.com/in/ada-lovelace/",
                "schema": {
                    "fields": [
                        {"to": "identity.name", "from": "fullName"},
                        {"to": "identity.headline", "from": "headline"},
                    ]
                },
            },
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 200
        assert response.json()["data"] == {
            "identity": {
                "name": "Ada Lovelace",
                "headline": "Mathematician and first computer programmer",
            }
        }


def test_custom_adapter_without_schema_returns_400(settings: Settings, dash_payload: dict) -> None:
    with _client(settings) as client:
        client.app.state.linkedin.fetch_profile = AsyncMock(return_value=dash_payload)
        response = client.post(
            "/v1/profile?adapter=custom",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_schema"


def test_get_profile_custom_adapter_returns_400(settings: Settings) -> None:
    with _client(settings) as client:
        response = client.get(
            "/v1/profile",
            params={"url": "https://www.linkedin.com/in/ada-lovelace/", "adapter": "custom"},
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "invalid_schema"


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


def test_post_accepts_browser_session_without_server_cookies(dash_payload: dict) -> None:
    token = "VISITOR_LI_AT_TOKEN_DO_NOT_LEAK"
    empty = Settings(linkedin_li_at="", linkedin_jsessionid="", api_key="")
    with _client(empty) as client:
        with patch("app.routers.profile.LinkedInClient") as mock_cls:
            instance = mock_cls.return_value
            instance.configured = True
            instance.fetch_profile = AsyncMock(return_value=dash_payload)
            instance.close = AsyncMock()
            response = client.post(
                "/v1/profile",
                json={
                    "url": "https://www.linkedin.com/in/ada-lovelace/",
                    "session": {
                        "liAt": token,
                        "jsessionid": "ajax:1",
                        "userAgent": "TestBrowser/1.0",
                    },
                },
            )
        assert response.status_code == 200
        assert response.json()["data"]["fullName"] == "Ada Lovelace"
        assert token not in response.text
        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["li_at"] == token
        assert kwargs["user_agent"] == "TestBrowser/1.0"
        instance.close.assert_awaited()


def test_post_without_any_session_returns_503() -> None:
    empty = Settings(linkedin_li_at="", linkedin_jsessionid="", api_key="")
    with _client(empty) as client:
        response = client.post(
            "/v1/profile",
            json={"url": "https://www.linkedin.com/in/ada-lovelace/"},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "not_configured"


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
