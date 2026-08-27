from fastapi.testclient import TestClient

from app.config import Settings
from app.exceptions import LinkedInError
from app.linkedin.client import LinkedInClient
from app.main import create_app
from app.security import redact


def test_settings_repr_hides_session_secrets() -> None:
    settings = Settings(
        linkedin_li_at="super-secret-li-at-token",
        linkedin_jsessionid="ajax:999999999",
        api_key="my-api-key-value",
    )
    dumped = repr(settings)
    assert "super-secret-li-at-token" not in dumped
    assert "ajax:999999999" not in dumped
    assert "my-api-key-value" not in dumped


def test_linkedin_client_repr_hides_cookies() -> None:
    client = LinkedInClient("li-at-secret", "ajax:42", "deco", extra_cookies={"bcookie": "v=secret"})
    text = repr(client)
    assert "li-at-secret" not in text
    assert "ajax:42" not in text
    assert "v=secret" not in text
    assert "configured=True" in text


def test_redact_replaces_known_secrets() -> None:
    secrets = ["li-at-secret", "ajax:42"]
    message = "boom li-at-secret and cookie ajax:42"
    assert redact(message, secrets) == "boom [REDACTED] and cookie [REDACTED]"


def test_api_responses_never_include_session_cookies() -> None:
    token = "UNIQUE_LI_AT_LEAK_TEST_TOKEN_12345"
    jsid = "ajax:LEAKTEST987654321"
    settings = Settings(linkedin_li_at=token, linkedin_jsessionid=jsid, api_key="k")
    with TestClient(create_app(settings)) as client:
        for path in ("/health", "/ui/config", "/v1/adapters", "/docs", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 200
            body = response.text
            assert token not in body
            assert jsid not in body
            assert "UNIQUE_LI_AT" not in body


def test_error_handler_redacts_secrets_in_messages() -> None:
    token = "UNIQUE_ERR_REDACT_TOKEN_XYZ"
    settings = Settings(linkedin_li_at=token, linkedin_jsessionid="ajax:1", api_key="")

    app = create_app(settings)

    @app.get("/_test_leak")
    async def _leak() -> None:
        raise LinkedInError(f"upstream failed with {token}")

    with TestClient(app) as client:
        response = client.get("/_test_leak")
        assert response.status_code == 502
        body = response.json()
        assert token not in body["error"]
        assert token not in body["detail"]
        assert "[REDACTED]" in body["error"]
