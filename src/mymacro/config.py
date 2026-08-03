from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYMACRO_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./mymacro.db"
    app_title: str = "mymacro"
    debug: bool = False


settings = Settings()
