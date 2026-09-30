from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime environment name, e.g. development or production.
    ENVIRONMENT: str = "development"


settings = Settings()
