from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    linkedin_li_at: str = ""
    linkedin_jsessionid: str = ""
    linkedin_liap: str = ""
    linkedin_bcookie: str = ""
    linkedin_lidc: str = ""
    linkedin_li_a: str = ""
    api_key: str = ""
    cache_ttl_seconds: int = 900
    rate_limit_per_minute: int = 10
    decoration_id: str = (
        "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93"
    )

    @property
    def linkedin_configured(self) -> bool:
        return bool(self.linkedin_li_at and self.linkedin_jsessionid)

    def extra_linkedin_cookies(self) -> dict[str, str]:
        mapping = {
            "liap": self.linkedin_liap,
            "bcookie": self.linkedin_bcookie,
            "lidc": self.linkedin_lidc,
            "li_a": self.linkedin_li_a,
        }
        return {name: value.strip() for name, value in mapping.items() if value and value.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
