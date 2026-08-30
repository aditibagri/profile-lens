import os
from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.security import collect_secrets, plain_secret

_CLOUD_ENV_MARKERS = ("RENDER", "RAILWAY_ENVIRONMENT", "FLY_APP_NAME", "K_SERVICE")


def running_on_cloud() -> bool:
    """True on Render / Railway / Fly / Cloud Run — LinkedIn often rejects home cookies."""
    return any(os.environ.get(name) for name in _CLOUD_ENV_MARKERS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SecretStr keeps cookies/API keys out of repr()/logs if settings are printed.
    linkedin_li_at: SecretStr = SecretStr("")
    linkedin_jsessionid: SecretStr = SecretStr("")
    linkedin_liap: SecretStr = SecretStr("")
    linkedin_bcookie: SecretStr = SecretStr("")
    linkedin_lidc: SecretStr = SecretStr("")
    linkedin_li_a: SecretStr = SecretStr("")
    # Optional: paste the User-Agent from the same browser that minted the cookies.
    linkedin_user_agent: str = ""
    api_key: SecretStr = SecretStr("")
    cache_ttl_seconds: int = 900
    rate_limit_per_minute: int = 10
    decoration_id: str = (
        "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93"
    )
    # unset = auto (on locally, off on Render). Set true/false to override.
    linkedin_host_session_ui: str = ""

    @field_validator(
        "linkedin_li_at",
        "linkedin_jsessionid",
        "linkedin_liap",
        "linkedin_bcookie",
        "linkedin_lidc",
        "linkedin_li_a",
        "api_key",
        mode="before",
    )
    @classmethod
    def _coerce_secret(cls, value: object) -> object:
        if value is None:
            return ""
        return value

    @property
    def linkedin_configured(self) -> bool:
        return bool(plain_secret(self.linkedin_li_at) and plain_secret(self.linkedin_jsessionid))

    @property
    def host_session_for_ui(self) -> bool:
        """Whether the website may look up profiles using server cookies.

        Home-minted ``li_at`` cookies usually work on this machine and fail from
        a Render datacenter IP. The public site therefore asks visitors to connect.
        """
        if not self.linkedin_configured:
            return False
        flag = (self.linkedin_host_session_ui or "").strip().lower()
        if flag in {"1", "true", "yes", "on"}:
            return True
        if flag in {"0", "false", "no", "off"}:
            return False
        return not running_on_cloud()

    @property
    def api_key_value(self) -> str:
        return plain_secret(self.api_key)

    def linkedin_session_values(self) -> dict[str, str]:
        return {
            "li_at": plain_secret(self.linkedin_li_at),
            "jsessionid": plain_secret(self.linkedin_jsessionid),
        }

    def extra_linkedin_cookies(self) -> dict[str, str]:
        mapping = {
            "liap": plain_secret(self.linkedin_liap),
            "bcookie": plain_secret(self.linkedin_bcookie),
            "lidc": plain_secret(self.linkedin_lidc),
            "li_a": plain_secret(self.linkedin_li_a),
        }
        return {name: value for name, value in mapping.items() if value}

    def secrets_for_redaction(self) -> list[str]:
        return collect_secrets(
            self.linkedin_li_at,
            self.linkedin_jsessionid,
            self.linkedin_liap,
            self.linkedin_bcookie,
            self.linkedin_lidc,
            self.linkedin_li_a,
            self.api_key,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
