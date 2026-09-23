from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    git_sha: str = "dev"
    database_url: str = ""
    # Empty = mock gateway. After bot release 3.0 this points to the bot API.
    bot_api_url: str = ""
    bot_api_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
