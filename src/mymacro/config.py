import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYMACRO_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./mymacro.db"
    app_title: str = "mymacro"
    debug: bool = False
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_vision_model: str = "gpt-4o-mini"
    fatsecret_client_id: str | None = None
    fatsecret_client_secret: str | None = None
    fatsecret_token_url: str = "https://oauth.fatsecret.com/connect/token"
    fatsecret_api_url: str = "https://platform.fatsecret.com/rest/server.api"

    def resolved_openai_api_key(self) -> str | None:
        return self.openai_api_key or os.environ.get("OPENAI_API_KEY") or None

    def resolved_fatsecret_client_id(self) -> str | None:
        return self.fatsecret_client_id or os.environ.get("MYMACRO_FATSECRET_CLIENT_ID") or None

    def resolved_fatsecret_client_secret(self) -> str | None:
        return (
            self.fatsecret_client_secret
            or os.environ.get("MYMACRO_FATSECRET_CLIENT_SECRET")
            or None
        )


settings = Settings()
