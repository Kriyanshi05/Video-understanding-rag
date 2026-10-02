from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime environment name, e.g. development or production.
    ENVIRONMENT: str = "development"

    # Redis connection used by Celery as broker and result backend.
    redis_url: str = "redis://localhost:6379/0"

    # Qdrant vector database URL (REST API).
    qdrant_url: str = "http://localhost:6333"

    # Collection name where transcript chunk embeddings are stored.
    qdrant_collection: str = "video_chunks"

    # Google Gemini API key used for grounded, general, and visual answers.
    gemini_api_key: str


settings = Settings()
