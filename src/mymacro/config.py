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

    def resolved_openai_api_key(self) -> str | None:
        return self.openai_api_key or os.environ.get("OPENAI_API_KEY") or None


settings = Settings()
