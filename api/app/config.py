from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    git_sha: str = "dev"
    database_url: str = ""
    # Bot internal API (ownership, plans, payments) + Remnawave panel (live data).
    # Either URL empty = mock gateway with demo data.
    bot_api_url: str = ""
    bot_api_token: str = ""
    remnawave_api_url: str = ""
    remnawave_api_token: str = ""
    # Sub links from the panel get this scheme and host, as the bot does.
    subscription_base_url: str = "https://sub.crs-projects.com"

    # auth
    public_origin: str = "https://vpn.crs-projects.com"
    session_cookie: str = "__Host-sid"
    telegram_login_bot_token: str = ""
    telegram_bot_username: str = ""
    # shared with @crs_vpn_bot for /api/internal/tg-login/*
    site_internal_token: str = ""
    webauthn_rp_id: str = "vpn.crs-projects.com"
    webauthn_rp_name: str = "CRS VPN"

    # mail; empty host = letters stay in web.outbox
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def cookie_secure(self) -> bool:
        return self.public_origin.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
