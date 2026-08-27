from pathlib import Path

import pytest

from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def dash_payload() -> dict:
    import json

    return json.loads((FIXTURES / "profile_dash.json").read_text())


@pytest.fixture
def profile_view_payload() -> dict:
    import json

    return json.loads((FIXTURES / "profile_view.json").read_text())


@pytest.fixture
def settings() -> Settings:
    return Settings(
        linkedin_li_at="test-li-at",
        linkedin_jsessionid="ajax:123456",
        api_key="test-key",
        cache_ttl_seconds=60,
        rate_limit_per_minute=30,
    )
