from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime environment name, e.g. development or production.
    ENVIRONMENT: str = "development"

    # Redis connection used by Celery as broker and result backend.
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
